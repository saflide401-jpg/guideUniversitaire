# Démonstration EXÉCUTABLE du pipeline avec des modèles PUBLICS génériques,
# en l'absence des trois modèles CamemBERT fine-tunés spécifiques au domaine RH
# (./models/camembert-ner, ./models/camembert-classification-secteur et
# ./models/camembert-classification-categorie, référencés par job_analyzer.py,
# qui n'existent pas encore chez l'utilisateur).
#
# Sert uniquement à prouver que l'architecture (spaCy comme squelette + composants
# personnalisés @Language.component déléguant à des modèles HuggingFace) fonctionne
# réellement de bout en bout. À remplacer par JobAnalyzerPipeline dès que les trois
# modèles fine-tunés sur un corpus d'offres annoté sont disponibles : la mécanique
# (closures, Language.component, extensions Doc) reste identique.

import json
import re

import torch
import spacy
from spacy.language import Language
from spacy.tokens import Doc
from transformers import pipeline as hf_pipeline

if not Doc.has_extension("entites_brutes"):
    Doc.set_extension("entites_brutes", default=None)
if not Doc.has_extension("secteur_offre"):
    Doc.set_extension("secteur_offre", default=None)
if not Doc.has_extension("categorie_emploi_offre"):
    Doc.set_extension("categorie_emploi_offre", default=None)


# Aucun modèle public n'a été fine-tuné sur des labels METIER/TYPE_CONTRAT/
# COMPETENCE/DIPLOME (c'est justement pour ça qu'un fine-tuning dédié est prévu
# dans l'architecture cible) : on donne donc aux deux classifications zero-shot
# une liste de labels candidats à la place d'un classifieur entraîné sur des
# labels fixes. Notons que le NER générique public reconnaît nativement ORG et
# LOC, ce qui couvre déjà correctement ENTREPRISE et LOCALISATION sans avoir
# besoin d'un fine-tuning dédié pour ces deux-là.
SECTEURS_CANDIDATS = [
    "Informatique / Développement",
    "Finance / Comptabilité",
    "Juridique",
    "Marketing / Commercial",
    "BTP / Génie Civil",
    "Ressources Humaines",
]
CATEGORIES_EMPLOI_CANDIDATES = [
    "CDI",
    "CDD",
    "Stage",
    "Alternance",
    "Freelance",
    "Temps partiel",
]


class JobAnalyzerPipelineDemo:
    """
    Même architecture que JobAnalyzerPipeline (job_analyzer.py), avec des modèles
    PUBLICS à la place des trois CamemBERT fine-tunés sur le domaine RH :
      - NER  : "Jean-Baptiste/camembert-ner" -> entités génériques PER/ORG/LOC/MISC
        (ORG/LOC couvrent ENTREPRISE/LOCALISATION ; pas de label METIER/TYPE_CONTRAT/
        COMPETENCE/DIPLOME, faute de fine-tuning dédié)
      - 2 classifications : zero-shot via "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
        une pour le secteur (SECTEURS_CANDIDATS), une pour la catégorie d'emploi
        (CATEGORIES_EMPLOI_CANDIDATES), toutes deux données à l'inférence plutôt
        qu'apprises à l'entraînement
    """

    def __init__(self, spacy_model: str = "fr_core_news_sm"):
        self.device = 0 if torch.cuda.is_available() else -1
        print(f"[Demo] Modèles chargés sur : {'GPU (cuda:0)' if self.device == 0 else 'CPU'}")

        self._ner_pipeline = hf_pipeline(
            task="ner",
            model="Jean-Baptiste/camembert-ner",
            aggregation_strategy="simple",
            device=self.device,
        )
        self._classification_pipeline = hf_pipeline(
            task="zero-shot-classification",
            model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
            device=self.device,
        )

        self.nlp = spacy.load(spacy_model, disable=["ner"])
        self._enregistrer_composants()

    def _enregistrer_composants(self) -> None:
        def composant_ner(doc: Doc) -> Doc:
            doc._.entites_brutes = self._ner_pipeline(doc.text)
            return doc

        def composant_secteur(doc: Doc) -> Doc:
            resultat = self._classification_pipeline(doc.text, candidate_labels=SECTEURS_CANDIDATS)
            doc._.secteur_offre = {
                "label": resultat["labels"][0],
                "score": round(float(resultat["scores"][0]), 4),
            }
            return doc

        def composant_categorie_emploi(doc: Doc) -> Doc:
            resultat = self._classification_pipeline(doc.text, candidate_labels=CATEGORIES_EMPLOI_CANDIDATES)
            doc._.categorie_emploi_offre = {
                "label": resultat["labels"][0],
                "score": round(float(resultat["scores"][0]), 4),
            }
            return doc

        Language.component("demo_ner_component", func=composant_ner)
        Language.component("demo_secteur_component", func=composant_secteur)
        Language.component("demo_categorie_emploi_component", func=composant_categorie_emploi)
        self.nlp.add_pipe("demo_ner_component", last=True)
        self.nlp.add_pipe("demo_secteur_component", last=True)
        self.nlp.add_pipe("demo_categorie_emploi_component", last=True)

    @staticmethod
    def _nettoyer_texte(texte: str) -> str:
        return re.sub(r"\s+", " ", texte.replace("\xa0", " ")).strip()

    def analyser(self, texte_offre: str) -> dict:
        doc = self.nlp(self._nettoyer_texte(texte_offre))
        entites = [
            {"texte": e["word"], "type": e["entity_group"], "score": round(float(e["score"]), 4)}
            for e in doc._.entites_brutes
        ]
        return {
            "entites_generiques_PER_ORG_LOC_MISC": entites,
            "secteur": doc._.secteur_offre,
            "categorie_emploi": doc._.categorie_emploi_offre,
            "note": (
                "Démo avec modèles publics génériques : NER sans labels métier/type de contrat/"
                "compétence/diplôme (fine-tuning dédié requis), classifications en zero-shot faute "
                "de classifieurs entraînés sur des labels fixes."
            ),
        }


if __name__ == "__main__":
    OFFRE_EXEMPLE = """
    Nous recherchons un Développeur Python Senior en CDI pour rejoindre l'équipe Data de
    STORM GROUP. Vous maîtrisez Python, Django et SQL, et avez une bonne connaissance
    de Docker ainsi que des bases en Machine Learning. Un Master en Informatique
    (Bac+5) est requis. Anglais courant apprécié. Poste basé à Ouagadougou, Burkina Faso.
    """
    pipeline = JobAnalyzerPipelineDemo()
    resultat = pipeline.analyser(OFFRE_EXEMPLE)
    print(json.dumps(resultat, ensure_ascii=False, indent=2))
