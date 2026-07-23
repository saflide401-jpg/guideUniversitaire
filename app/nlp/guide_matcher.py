# app/nlp/guide_matcher.py
#
# Fait correspondre le titre d'une offre d'emploi scrapée (OffreEmploi.titre_poste)
# à un métier du guide d'orientation (guide_orientation.json), pour proposer à
# l'utilisateur la filière universitaire et les centres de formation permettant
# d'accéder à ce type de poste.
#
# Le NER CamemBERT (job_analyzer.py) n'est pas branché sur le flux de scraping
# réel (voir RAPPORT_PROJET.md, section 5.6 : "chantier en cours d'intégration") :
# aucun champ "métier" nettoyé n'existe en base pour les offres déjà collectées.
# On matche donc directement sur titre_poste, seul champ texte disponible pour
# la totalité des offres, via une similarité floue plutôt qu'une égalité stricte
# (un titre scrapé du type "Ingénieur Système & réseaux informatiques" ne
# correspondra jamais mot pour mot à un intitulé du guide comme "Architecte Cloud").

import difflib
import json
import os
import re
import unicodedata

_GUIDE_PATH = os.path.join(os.path.dirname(__file__), "guide_orientation.json")

# En dessous de ce score, on préfère ne renvoyer aucune correspondance plutôt
# qu'une correspondance non pertinente affichée comme si elle faisait autorité.
SEUIL_CONFIANCE = 0.30

_MOTS_VIDES = {
    "un", "une", "des", "de", "du", "le", "la", "les", "et", "ou", "en", "au", "aux",
    "pour", "avec", "sans", "sur", "dans", "chez", "poste", "offre", "recherche",
    "h", "f", "hf", "cdi", "cdd",
    # Intitulés de fonction trop génériques pour discriminer entre les 100 métiers du
    # guide à eux seuls (ex: "Ingénieur Système & réseaux" et "Ingénieur en Mines" ne
    # partagent que le mot "ingénieur", sans rapport réel) : on ne matche que sur les
    # mots réellement distinctifs (domaine, technologie, spécialité).
    "ingenieur", "ingenieure", "responsable", "chef", "assistant", "assistante",
    "directeur", "directrice", "charge", "chargee", "technicien", "technicienne",
    "agent", "agente", "specialiste", "expert", "experte", "conseiller", "conseillere",
    "gestionnaire", "coordinateur", "coordinatrice", "manager", "consultant", "consultante",
    "analyste", "professionnel", "professionnelle",
    # "securite" seul est trop polysemique (informatique vs alimentaire vs gardiennage vs
    # routiere) pour departager entre les metiers du guide qui le contiennent tous les
    # trois : mieux vaut ne pas matcher que matcher au hasard l'un des trois domaines.
    "securite",
}


def _sans_accents(texte):
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


def _normaliser(texte):
    texte = _sans_accents(texte.lower())
    texte = re.sub(r"[^\w\s]", " ", texte)
    mots = [m for m in texte.split() if m not in _MOTS_VIDES]
    return " ".join(mots)


def _score_similarite(titre_norm, metier_norm):
    tokens_titre = {m for m in titre_norm.split() if len(m) >= 3}
    tokens_metier = {m for m in metier_norm.split() if len(m) >= 3}
    if not tokens_titre or not tokens_metier:
        return 0.0

    intersection = tokens_titre & tokens_metier
    union = tokens_titre | tokens_metier
    jaccard = len(intersection) / len(union)

    ratio_sequence = difflib.SequenceMatcher(None, titre_norm, metier_norm).ratio()

    return 0.7 * jaccard + 0.3 * ratio_sequence


class GuideOrientationMatcher:
    """Charge le guide d'orientation une seule fois et matche des titres d'offres."""

    def __init__(self, guide_path=_GUIDE_PATH):
        with open(guide_path, encoding="utf-8") as f:
            data = json.load(f)

        # Aplatit la structure par domaine en une liste plate de métiers, chacun
        # gardant une référence à son domaine d'origine pour l'affichage.
        self._metiers = []
        for domaine in data["domaines"]:
            for metier in domaine["metiers"]:
                self._metiers.append({**metier, "domaine": domaine["nom"]})

        self._metiers_norm = [_normaliser(m["nom"]) for m in self._metiers]

    def matcher(self, titre_poste):
        """
        Retourne le métier du guide le plus proche de `titre_poste`, avec son score
        de confiance, ou None si aucun métier ne dépasse le seuil de confiance.
        """
        if not titre_poste:
            return None

        titre_norm = _normaliser(titre_poste)
        if not titre_norm:
            return None

        meilleur_score = 0.0
        meilleur_metier = None
        for metier, metier_norm in zip(self._metiers, self._metiers_norm):
            score = _score_similarite(titre_norm, metier_norm)
            if score > meilleur_score:
                meilleur_score = score
                meilleur_metier = metier

        if meilleur_score < SEUIL_CONFIANCE:
            return None

        return {**meilleur_metier, "score_confiance": round(meilleur_score, 3)}


_instance = None


def get_matcher():
    """Retourne une instance partagée (le guide ne change pas en cours d'exécution)."""
    global _instance
    if _instance is None:
        _instance = GuideOrientationMatcher()
    return _instance
