# app/nlp/retraduire_offres_existantes.py
#
# Script ponctuel : traduit en français les offres déjà en base dont la
# description est détectée en anglais, et met à jour leur `langue_originale`.
# À exécuter une seule fois après l'ajout de la traduction automatique
# (`app/nlp/traducteur.py`) pour rattraper les offres collectées avant ce
# changement — les nouvelles offres sont traduites au fil de l'eau par
# `ScrapingService`, ce script ne sert qu'au stock déjà en base.
#
# Usage (depuis la racine du projet, avec le même .env que l'application) :
#   python -m app.nlp.retraduire_offres_existantes

import csv
from datetime import datetime

from flask import Flask

from config import Config
from app import db
from app.models import OffreEmploi
from app.nlp.traducteur import traduire_si_anglais


def retraduire():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        # Seules les offres encore marquées "fr" (valeur par défaut posée par la
        # migration) sont candidates : une offre déjà marquée "en" a déjà été
        # traduite par une exécution précédente de ce script ou par la collecte.
        offres = OffreEmploi.query.filter(OffreEmploi.langue_originale == "fr").all()
        print(f"{len(offres)} offre(s) à vérifier...")

        # Sauvegarde du texte original avant écrasement : la traduction remplace
        # titre_poste/description en base (un seul champ, pas de colonne dédiée au
        # texte source), donc sans cette sauvegarde le texte anglais d'origine
        # serait perdu de façon irréversible.
        nom_sauvegarde = f"sauvegarde_avant_traduction_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        lignes_sauvegarde = []

        nb_traduites = 0
        for offre in offres:
            titre_fr, description_fr, langue = traduire_si_anglais(offre.titre_poste, offre.description)
            if langue == "en":
                print(f"Traduite : {offre.titre_poste[:60]}")
                lignes_sauvegarde.append({
                    "id_offre": offre.id_offre,
                    "titre_poste_original": offre.titre_poste,
                    "description_originale": offre.description,
                })
                offre.titre_poste = titre_fr
                offre.description = description_fr
                offre.langue_originale = "en"
                nb_traduites += 1

        if lignes_sauvegarde:
            with open(nom_sauvegarde, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["id_offre", "titre_poste_original", "description_originale"])
                writer.writeheader()
                writer.writerows(lignes_sauvegarde)
            print(f"\nTexte original sauvegardé dans {nom_sauvegarde} avant écrasement.")

        db.session.commit()
        print(f"{nb_traduites} offre(s) traduite(s) sur {len(offres)} vérifiée(s).")


if __name__ == "__main__":
    retraduire()
