# app/nlp/pre_annoter_corpus.py
#
# Prépare un fichier prêt à annoter à partir du corpus collecté
# (`collecte_corpus.py`) : pour chaque offre, exécute le pipeline générique
# (NER + classification zero-shot, mêmes modèles publics que
# `demo_pipeline_generique.py`) afin de PRÉ-REMPLIR des suggestions à
# corriger par un humain — annoter par correction plutôt qu'à blanc
# (section 5.7/7 du rapport). Aucune suggestion produite ici n'est une
# vérité terrain, y compris quand le modèle est confiant.
#
# Contrairement à demo_pipeline_generique.py (dont la liste de secteurs
# candidats sert uniquement à sa propre démonstration déjà documentée,
# section 5.6 du rapport), ce script utilise ses propres listes de
# candidats alignées sur les 13 catégories cibles du notebook
# d'entraînement (SECTOR_LABELS) et les 6 types de contrat
# (CATEGORIE_LABELS), pour que les suggestions soient directement
# comparables aux labels que le modèle fine-tuné devra produire.
#
# Échantillonnage équilibré : plutôt que de pré-annoter les 500+ offres du
# corpus (long sur CPU, et inutile — un échantillon annoté suffit), un
# nombre maximum d'offres par catégorie suggérée est prélevé, pour éviter
# que l'échantillon ne reproduise le déséquilibre du corpus brut (voir
# RAPPORT_PROJET.md, section 5.6 : Informatique y concentre 36 % du volume).
#
# Usage (depuis la racine du projet) :
#   python -m app.nlp.pre_annoter_corpus corpus_offres_burkina_20260720_1954.csv
#   python -m app.nlp.pre_annoter_corpus corpus_offres_burkina_20260720_1954.csv --max-par-categorie 15

import sys
import csv
from collections import defaultdict

import torch
from transformers import pipeline as hf_pipeline

SECTEURS_CIBLES = [
    "Informatique", "BTP_Genie_Civil", "Comptabilite_Finance", "Mines_Industrie",
    "Agriculture", "ONG_Social", "Microfinance_Banque", "Marketing_Commercial",
    "Juridique", "Ressources_Humaines", "Education", "Sante", "Logistique",
]
CATEGORIES_CONTRAT_CIBLES = ["CDI", "CDD", "Stage", "Alternance", "Freelance", "Temps_Partiel"]

MAX_PAR_CATEGORIE_DEFAUT = 25
LONGUEUR_MAX_TEXTE = 2000  # troncature raisonnable pour le zero-shot (evite les descriptions demesurees)

COLONNES_SORTIE = [
    "id_externe", "titre_poste", "nom_entreprise", "localisation", "description",
    "source", "mots_cles_recherche",
    "secteur_suggere", "confiance_suggestion",
    "secteur_zero_shot", "score_secteur_zero_shot", "accord_secteur",
    "categorie_contrat_zero_shot", "score_categorie_zero_shot",
    "entites_detectees",
    # Colonnes volontairement vides : c'est ici que l'annotateur humain corrige
    # ou confirme, jamais les colonnes de suggestion ci-dessus.
    "secteur_final", "categorie_contrat_finale", "entites_finales_bio",
]


def selectionner_echantillon_equilibre(lignes, max_par_categorie):
    """
    Prélève au plus `max_par_categorie` offres par secteur suggéré, en
    priorisant les suggestions de confiance "haute" avant "a_verifier",
    pour constituer un échantillon d'annotation plus équilibré que le
    corpus brut (dominé par Informatique).
    """
    par_categorie = defaultdict(list)
    for ligne in lignes:
        cle = ligne.get("secteur_suggere") or "(non_categorise)"
        par_categorie[cle].append(ligne)

    echantillon = []
    for cle, groupe in par_categorie.items():
        groupe_trie = sorted(groupe, key=lambda l: l.get("confiance_suggestion") != "haute")
        echantillon.extend(groupe_trie[:max_par_categorie])

    return echantillon


def charger_pipelines():
    device = 0 if torch.cuda.is_available() else -1
    print(f"Modèles chargés sur : {'GPU' if device == 0 else 'CPU'} (CPU : plus lent, prévoir du temps par offre)")
    ner_pipeline = hf_pipeline(
        task="ner", model="Jean-Baptiste/camembert-ner", aggregation_strategy="simple", device=device
    )
    classification_pipeline = hf_pipeline(
        task="zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", device=device
    )
    return ner_pipeline, classification_pipeline


def pre_annoter(lignes):
    ner_pipeline, classification_pipeline = charger_pipelines()
    resultats = []

    for i, ligne in enumerate(lignes):
        texte = f"{ligne['titre_poste']}. {ligne['description']}"[:LONGUEUR_MAX_TEXTE]
        print(f"[{i + 1}/{len(lignes)}] {ligne['titre_poste'][:60]}")

        secteur_zs = classification_pipeline(texte, candidate_labels=SECTEURS_CIBLES)
        categorie_zs = classification_pipeline(texte, candidate_labels=CATEGORIES_CONTRAT_CIBLES)
        entites = ner_pipeline(texte)

        secteur_zero_shot = secteur_zs["labels"][0]
        secteur_mapping = ligne.get("secteur_suggere", "")
        accord = "n/a" if not secteur_mapping else ("oui" if secteur_mapping == secteur_zero_shot else "non")

        ligne.update({
            "secteur_zero_shot": secteur_zero_shot,
            "score_secteur_zero_shot": round(float(secteur_zs["scores"][0]), 3),
            "accord_secteur": accord,
            "categorie_contrat_zero_shot": categorie_zs["labels"][0],
            "score_categorie_zero_shot": round(float(categorie_zs["scores"][0]), 3),
            "entites_detectees": " | ".join(f"{e['entity_group']}:{e['word']}" for e in entites),
            "secteur_final": "",
            "categorie_contrat_finale": "",
            "entites_finales_bio": "",
        })
        resultats.append(ligne)

    return resultats


def exporter(resultats, chemin_corpus):
    nom_sortie = chemin_corpus.rsplit(".", 1)[0] + "_pre_annote.csv"
    with open(nom_sortie, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES_SORTIE)
        writer.writeheader()
        writer.writerows(resultats)
    print(f"\n{len(resultats)} offres pré-annotées exportées dans {nom_sortie}")
    return nom_sortie


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python -m app.nlp.pre_annoter_corpus <fichier_corpus.csv> [--max-par-categorie N]")
        sys.exit(1)

    chemin = sys.argv[1]
    max_par_categorie = MAX_PAR_CATEGORIE_DEFAUT
    if "--max-par-categorie" in sys.argv:
        max_par_categorie = int(sys.argv[sys.argv.index("--max-par-categorie") + 1])

    with open(chemin, encoding="utf-8-sig") as f:
        toutes_les_lignes = list(csv.DictReader(f))

    echantillon = selectionner_echantillon_equilibre(toutes_les_lignes, max_par_categorie)
    print(f"Échantillon équilibré : {len(echantillon)} offres sur {len(toutes_les_lignes)} (max {max_par_categorie}/catégorie)\n")

    exporter(pre_annoter(echantillon), chemin)
