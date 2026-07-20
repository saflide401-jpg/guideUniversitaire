# Pipeline NLP hybride : spaCy sert de squelette (prétraitement, orchestration,
# extensibilité) et trois modèles CamemBERT fine-tunés font l'inférence lourde
# (NER + 2 classifications de séquence), encapsulés dans des composants spaCy
# personnalisés. Ainsi le pipeline reste un objet spaCy standard (sérialisable,
# inspectable, extensible avec d'autres étapes plus tard) tout en profitant de
# la qualité d'un transformer entraîné spécifiquement sur du texte en français.

import re
import json

import torch
import spacy
from spacy.language import Language
from spacy.tokens import Doc
from transformers import pipeline as hf_pipeline


# On étend l'objet Doc de spaCy pour qu'il transporte les résultats des modèles
# CamemBERT tout au long du pipeline, exactement comme le ferait un composant
# natif (doc.ents, doc.cats, ...). Déclaré au niveau module pour n'être exécuté
# qu'une seule fois, même si plusieurs instances de JobAnalyzerPipeline sont créées.
if not Doc.has_extension("entites_offre"):
    Doc.set_extension("entites_offre", default=None)
if not Doc.has_extension("secteur_offre"):
    Doc.set_extension("secteur_offre", default=None)
if not Doc.has_extension("categorie_emploi_offre"):
    Doc.set_extension("categorie_emploi_offre", default=None)


class JobAnalyzerPipeline:
    """
    Transforme le texte brut d'une offre d'emploi en dictionnaire structuré :
    métier, type de contrat, entreprise, localisation, compétences, diplôme
    requis, secteur d'activité et catégorie d'emploi.

    Architecture : un pipeline spaCy dont le NER natif est désactivé et remplacé
    par trois composants personnalisés qui délèguent l'inférence à des modèles
    CamemBERT chargés une seule fois à l'instanciation (coûteux à charger,
    bon marché à appeler ensuite) :
      1. NER          -> METIER, TYPE_CONTRAT, ENTREPRISE, LOCALISATION, COMPETENCE, DIPLOME
      2. Classification -> secteur d'activité (Informatique, Juridique, ...)
      3. Classification -> catégorie d'emploi (CDI, CDD, Stage, Alternance, Freelance, Temps partiel)

    Secteur et catégorie d'emploi sont deux modèles distincts plutôt qu'un seul
    label combiné : ce sont deux questions indépendantes sur la même offre
    ("dans quel domaine ?" vs "quel type de contrat ?"), et les garder séparées
    évite de multiplier artificiellement le nombre de classes à apprendre.
    """

    # Les modèles NER fine-tunés HuggingFace renvoient des labels BIO fusionnés
    # (grâce à aggregation_strategy="simple") : ce sont les seules clés que l'on
    # sait interpréter en aval.
    TYPES_ENTITES_CONNUS = (
        "METIER", "TYPE_CONTRAT", "ENTREPRISE", "LOCALISATION", "COMPETENCE", "DIPLOME",
    )

    def __init__(
        self,
        ner_model_path: str = "./models/camembert-ner",
        secteur_model_path: str = "./models/camembert-classification-secteur",
        categorie_emploi_model_path: str = "./models/camembert-classification-categorie",
        spacy_model: str = "fr_core_news_sm",
    ):
        # -1 = CPU, 0 = premier GPU visible : c'est la convention attendue par
        # le paramètre `device` des pipelines HuggingFace (pas un simple booléen).
        self.device = 0 if torch.cuda.is_available() else -1
        print(
            f"[JobAnalyzerPipeline] Modèles chargés sur : "
            f"{'GPU (cuda:0)' if self.device == 0 else 'CPU'}"
        )

        # --- Chargement des trois modèles CamemBERT fine-tunés (une seule fois) ---
        # aggregation_strategy="simple" reconstitue les entités complètes à partir
        # des sous-tokens (wordpieces) et des tags B-/I- bruts du modèle, ce qui
        # évite de réimplémenter cette logique de fusion à la main.
        self._ner_pipeline = hf_pipeline(
            task="ner",
            model=ner_model_path,
            tokenizer=ner_model_path,
            aggregation_strategy="simple",
            device=self.device,
        )
        self._secteur_pipeline = hf_pipeline(
            task="text-classification",
            model=secteur_model_path,
            tokenizer=secteur_model_path,
            device=self.device,
        )
        self._categorie_emploi_pipeline = hf_pipeline(
            task="text-classification",
            model=categorie_emploi_model_path,
            tokenizer=categorie_emploi_model_path,
            device=self.device,
        )

        # --- Squelette spaCy ---
        # On désactive le NER natif de spaCy : les modèles CamemBERT le remplacent
        # entièrement. spaCy reste utile comme tokenizer/segmenteur de phrases et
        # comme conteneur de pipeline extensible (on pourrait ajouter demain un
        # composant de lemmatisation ou de détection de langue sans rien casser).
        self.nlp = spacy.load(spacy_model, disable=["ner"])
        self._enregistrer_composants_personnalises()

    def _enregistrer_composants_personnalises(self) -> None:
        """
        Enregistre les trois composants CamemBERT dans le pipeline spaCy.

        On définit ici des fermetures (closures) qui capturent `self` plutôt que
        des fonctions module-level : les pipelines HuggingFace sont des objets
        lourds et stateful (poids du modèle en mémoire), propres à CETTE instance
        de JobAnalyzerPipeline. Language.component accepte un appel direct
        (func=...) en plus de l'usage en décorateur, ce qui permet justement
        d'enregistrer une closure liée à l'instance plutôt qu'une fonction globale.
        """

        def composant_ner(doc: Doc) -> Doc:
            resultats_bruts = self._ner_pipeline(doc.text)
            doc._.entites_offre = self._structurer_entites(resultats_bruts)
            return doc

        def composant_secteur(doc: Doc) -> Doc:
            resultat = self._secteur_pipeline(doc.text)[0]
            doc._.secteur_offre = {
                "label": resultat["label"],
                "score": round(float(resultat["score"]), 4),
            }
            return doc

        def composant_categorie_emploi(doc: Doc) -> Doc:
            resultat = self._categorie_emploi_pipeline(doc.text)[0]
            doc._.categorie_emploi_offre = {
                "label": resultat["label"],
                "score": round(float(resultat["score"]), 4),
            }
            return doc

        Language.component("camembert_ner_component", func=composant_ner)
        Language.component("camembert_secteur_component", func=composant_secteur)
        Language.component("camembert_categorie_emploi_component", func=composant_categorie_emploi)

        self.nlp.add_pipe("camembert_ner_component", last=True)
        self.nlp.add_pipe("camembert_secteur_component", last=True)
        self.nlp.add_pipe("camembert_categorie_emploi_component", last=True)

    @staticmethod
    def _nettoyer_texte(texte: str) -> str:
        """
        Nettoyage minimal avant inférence : les modèles transformers gèrent déjà
        la ponctuation et la casse via leur propre tokenizer, donc on se limite à
        éliminer ce qui n'apporte aucune information (espaces multiples, sauts de
        ligne de mise en forme LinkedIn) sans dénaturer le texte.
        """
        texte = texte.replace("\xa0", " ")  # espaces insécables fréquents dans le HTML scrapé
        texte = re.sub(r"\s+", " ", texte)
        return texte.strip()

    @classmethod
    def _structurer_entites(cls, resultats_ner: list) -> dict:
        """
        Regroupe la liste plate d'entités renvoyée par le modèle en dictionnaire
        {type: [entités]}, en dédupliquant les répétitions (une compétence citée
        plusieurs fois dans une offre) et en conservant le score de confiance
        maximum observé pour chaque valeur unique.
        """
        entites = {type_entite: [] for type_entite in cls.TYPES_ENTITES_CONNUS}

        for entite in resultats_ner:
            label = entite["entity_group"].upper()
            if label not in entites:
                continue  # entité hors périmètre (le modèle peut avoir d'autres labels)

            valeur = entite["word"].strip()
            score = round(float(entite["score"]), 4)

            existante = next(
                (e for e in entites[label] if e["valeur"].lower() == valeur.lower()),
                None,
            )
            if existante:
                existante["score"] = max(existante["score"], score)
            else:
                entites[label].append({"valeur": valeur, "score": score})

        return entites

    def analyser(self, texte_offre: str) -> dict:
        """
        Point d'entrée principal du pipeline : texte brut d'une offre -> dictionnaire
        structuré. C'est la seule méthode que le reste de l'application a besoin
        d'appeler (ex: ScrapingService pour enrichir une offre au moment du scraping).
        """
        texte_propre = self._nettoyer_texte(texte_offre)
        doc = self.nlp(texte_propre)
        entites = doc._.entites_offre

        return {
            "metier": [e["valeur"] for e in entites["METIER"]],
            "type_contrat": [e["valeur"] for e in entites["TYPE_CONTRAT"]],
            "entreprise": [e["valeur"] for e in entites["ENTREPRISE"]],
            "localisation": [e["valeur"] for e in entites["LOCALISATION"]],
            "competences": [e["valeur"] for e in entites["COMPETENCE"]],
            "diplome": [e["valeur"] for e in entites["DIPLOME"]],
            "secteur": doc._.secteur_offre,
            "categorie_emploi": doc._.categorie_emploi_offre,
            # Version détaillée avec scores de confiance : utile pour appliquer un
            # seuil de rejet en aval, ou pour débugger/justifier une extraction en soutenance.
            "entites_detaillees": entites,
        }


if __name__ == "__main__":
    # Exemple d'exécution avec une offre factice réaliste, à présenter en soutenance.
    # Nécessite au préalable :
    #   pip install spacy transformers torch
    #   python -m spacy download fr_core_news_sm
    # ainsi que les trois modèles CamemBERT fine-tunés présents aux chemins ci-dessous
    # (./models/camembert-ner, ./models/camembert-classification-secteur et
    # ./models/camembert-classification-categorie).
    OFFRE_EXEMPLE = """
    Nous recherchons un Développeur Python Senior en CDI pour rejoindre l'équipe
    Data de STORM GROUP. Vous maîtrisez Python, Django et SQL, et avez une bonne
    connaissance de Docker ainsi que des bases en Machine Learning. Un Master en
    Informatique (Bac+5) ou équivalent est requis. Anglais courant apprécié.
    Poste basé à Ouagadougou, Burkina Faso, à pourvoir immédiatement.
    """

    pipeline = JobAnalyzerPipeline()
    resultat = pipeline.analyser(OFFRE_EXEMPLE)
    print(json.dumps(resultat, ensure_ascii=False, indent=2))
