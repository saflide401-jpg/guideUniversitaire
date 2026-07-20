# app/nlp/traducteur.py
#
# Traduction automatique anglais -> français des offres collectées dont la
# source ne fournit le contenu qu'en anglais (fréquent pour les offres
# d'organisations internationales/ONG au Burkina Faso, ex. "Senior
# Climate-Resilient Infrastructure Expert" chez NTU International). Le public
# cible du projet est francophone (section 2.2 du rapport) : une offre non
# traduite resterait illisible pour lui.
#
# Détection de langue : `langdetect` (léger, aucun modèle à télécharger,
# fonctionne hors ligne).
# Traduction : modèle Hugging Face Helsinki-NLP/opus-mt-en-fr, qui réutilise
# les dépendances transformers/torch déjà présentes pour le pipeline NLP
# (section 5.6) plutôt que d'appeler une API de traduction payante externe.
# Chargé directement (tokenizer + modèle, pas `pipeline()` : transformers 5.x
# a retiré la tâche "translation" du registre des pipelines) une seule fois
# par processus, pas à chaque offre.

from langdetect import detect, LangDetectException

_tokenizer = None
_model = None

# Au-delà de cette longueur, un paragraphe est découpé par phrase avant
# traduction : le modèle MarianMT tronque silencieusement au-delà d'environ
# 512 tokens, ce qui couperait la traduction en plein milieu sans prévenir.
MAX_CARACTERES_PAR_MORCEAU = 800

MODELE_TRADUCTION = "Helsinki-NLP/opus-mt-en-fr"


def _get_modele():
    global _tokenizer, _model
    if _model is None:
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        _tokenizer = AutoTokenizer.from_pretrained(MODELE_TRADUCTION)
        _model = AutoModelForSeq2SeqLM.from_pretrained(MODELE_TRADUCTION)
    return _tokenizer, _model


def detecter_langue(texte):
    """Retourne le code langue détecté ('fr', 'en', ...), ou None si le texte est trop court pour être fiable."""
    if not texte or len(texte.strip()) < 20:
        return None
    try:
        return detect(texte)
    except LangDetectException:
        return None


def _traduire_morceau(texte):
    tokenizer, model = _get_modele()
    entrees = tokenizer(texte, return_tensors="pt", truncation=True, max_length=512)
    sortie = model.generate(**entrees, max_length=512)
    return tokenizer.decode(sortie[0], skip_special_tokens=True)


def _traduire_texte_long(texte):
    """Traduit un texte paragraphe par paragraphe, en découpant par phrase les paragraphes trop longs."""
    paragraphes_traduits = []
    for paragraphe in texte.split("\n"):
        if not paragraphe.strip():
            paragraphes_traduits.append(paragraphe)
            continue

        morceaux = (
            [paragraphe] if len(paragraphe) <= MAX_CARACTERES_PAR_MORCEAU
            else [m for m in paragraphe.split(". ") if m.strip()]
        )
        traductions = [_traduire_morceau(morceau[:MAX_CARACTERES_PAR_MORCEAU]) for morceau in morceaux]
        paragraphes_traduits.append(". ".join(traductions))

    return "\n".join(paragraphes_traduits)


def traduire_si_anglais(titre_poste, description):
    """
    Détecte la langue de la description et, si elle est en anglais, traduit
    le titre et la description en français.

    Returns:
        tuple[str, str, str]: (titre_poste, description, langue_originale).
        langue_originale vaut "en" si une traduction a eu lieu, sinon la
        langue détectée (ou "fr" par défaut si indétectable).
    """
    langue = detecter_langue(description)
    if langue != "en":
        return titre_poste, description, (langue or "fr")

    titre_traduit = _traduire_morceau(titre_poste[:MAX_CARACTERES_PAR_MORCEAU])
    description_traduite = _traduire_texte_long(description)

    return titre_traduit, description_traduite, "en"
