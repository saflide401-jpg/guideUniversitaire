# app/nlp/collecte_corpus.py
#
# Script de collecte du corpus d'entraînement, à exécuter en local (VSCode /
# terminal). Contrairement à une collecte dans Colab, ce script réutilise
# directement les vrais clients de scraping (app/scraping/), sans les
# dupliquer : toute correction qui leur est apportée est immédiatement
# reflétée ici.
#
# Le corpus combine deux sources :
# 1. Les offres déjà collectées dans la base Postgres de production
#    (gratuites : aucune requête réseau, données déjà réelles).
# 2. Une collecte fraîche via Emploi LeFaso.net et ICI Partenaires Entreprises,
#    pour dépasser le volume déjà en base.
# Les deux sont dédupliquées par identifiant externe (même colonne que
# `OffreEmploi.linkedin_job_id`), donc une offre déjà en base n'est jamais
# comptée deux fois même si la collecte fraîche la retrouve.
#
# Le scraping LinkedIn (Playwright) n'est volontairement pas repris pour la
# collecte fraîche : le corpus vise avant tout le Burkina Faso, déjà bien
# couvert par les deux sources `requests`, plus légères.
#
# Usage (depuis la racine du projet, avec le même .env que l'application —
# SECRET_KEY / DATABASE_URL requis, et la base Postgres accessible puisque ce
# script la lit désormais) :
#   python -m app.nlp.collecte_corpus
#
# Produit un fichier corpus_offres_burkina_AAAAMMJJ_HHMM.csv à la racine du
# projet, à annoter manuellement (Label Studio / doccano) avant de l'utiliser
# dans entrainement_colab.ipynb (section 7, "Passer à l'échelle").

import csv
from datetime import datetime

from flask import Flask

from config import Config
from app import db
from app.models import OffreEmploi, Entreprise
from app.scraping.lefaso_client import LefasoEmploiClient
from app.scraping.ici_pe_client import IciPeClient

MOTS_CLES_COLLECTE = [
    "informatique", "comptable", "ingénieur", "communication",
    "commercial", "logistique", "ressources humaines", "marketing",
    "juriste", "agronome",
]
LIMITE_PAR_RECHERCHE = 10  # même volume que la collecte planifiée de l'application (scheduler.py)

COLONNES_CSV = [
    "id_externe", "titre_poste", "nom_entreprise", "localisation",
    "description", "source", "mots_cles_recherche",
]


def recuperer_offres_db():
    """
    Récupère les offres déjà collectées en production (Postgres), pour enrichir
    gratuitement le corpus sans requête réseau supplémentaire.

    Construit sa propre instance Flask minimale (config + SQLAlchemy) plutôt que
    d'appeler `create_app()` : cette dernière enregistre les routes et démarre le
    planificateur de collecte automatique (`start_auto_scraping`), des effets de
    bord inutiles et indésirables pour un simple export en lecture seule.
    """
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        rows = db.session.query(
            OffreEmploi.linkedin_job_id, OffreEmploi.titre_poste, OffreEmploi.description,
            Entreprise.nom_entreprise, Entreprise.localisation,
        ).join(Entreprise, OffreEmploi.id_entreprise == Entreprise.id_entreprise).all()

    return [
        {
            "id_externe": row.linkedin_job_id,
            "titre_poste": row.titre_poste,
            "nom_entreprise": row.nom_entreprise,
            "localisation": row.localisation or "",
            "description": row.description or "Description non disponible.",
            "source": "base_production",
            "mots_cles_recherche": "",
        }
        for row in rows
    ]


def collecter():
    """Interroge Emploi LeFaso.net et ICI Partenaires Entreprises sur chaque mot-clé, dédupliquée."""
    lefaso_client = LefasoEmploiClient()
    ici_pe_client = IciPeClient()

    toutes_les_offres = []
    ids_vus = set()

    for mots_cles in MOTS_CLES_COLLECTE:
        for source_nom, client in [("lefaso", lefaso_client), ("ici_pe", ici_pe_client)]:
            print(f"[{source_nom}] Recherche : {mots_cles}")
            for offre in client.search_offres(mots_cles, limit=LIMITE_PAR_RECHERCHE):
                if offre["id_externe"] in ids_vus:
                    continue
                ids_vus.add(offre["id_externe"])
                offre["source"] = source_nom
                offre["mots_cles_recherche"] = mots_cles
                toutes_les_offres.append(offre)

    return toutes_les_offres


def construire_corpus():
    """Combine les offres déjà en base et une collecte fraîche, dédupliquées par identifiant externe."""
    print("Récupération des offres déjà en base (production)...")
    offres = recuperer_offres_db()
    print(f"{len(offres)} offres récupérées depuis la base.\n")

    ids_vus = {o["id_externe"] for o in offres}
    for offre in collecter():
        if offre["id_externe"] not in ids_vus:
            ids_vus.add(offre["id_externe"])
            offres.append(offre)

    return offres


def exporter_csv(offres):
    """Écrit les offres collectées dans un fichier CSV horodaté, à la racine du projet."""
    nom_fichier = f"corpus_offres_burkina_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    with open(nom_fichier, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES_CSV)
        writer.writeheader()
        writer.writerows(offres)

    print(f"\n{len(offres)} offres uniques exportées dans {nom_fichier}")
    return nom_fichier


if __name__ == "__main__":
    exporter_csv(construire_corpus())
