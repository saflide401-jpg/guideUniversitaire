# app/lancer_collecte_manuelle.py
#
# Utilitaire de développement : déclenche une collecte ponctuelle depuis le
# terminal, pour tester une source sans attendre le planificateur automatique
# (scheduler.py) ni le démarrer. Ne remplace pas la collecte automatique de
# production (section 1.3 du rapport : l'utilisateur final ne déclenche
# jamais lui-même une collecte) — cet outil est réservé au développement.
#
# Usage (depuis la racine du projet, avec le même .env que l'application) :
#   python -m app.lancer_collecte_manuelle linkedin "Développeur Python" Ouagadougou
#   python -m app.lancer_collecte_manuelle lefaso informatique
#   python -m app.lancer_collecte_manuelle ici_pe informatique

import sys

from flask import Flask

from config import Config
from app import db
from app.services import ScrapingService


def main():
    if len(sys.argv) < 3:
        print("Usage : python -m app.lancer_collecte_manuelle <linkedin|lefaso|ici_pe> <mots-clés> [lieu]")
        sys.exit(1)

    source = sys.argv[1]
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    scraping_service = ScrapingService()

    with app.app_context():
        if source == "linkedin":
            if len(sys.argv) < 4:
                print("Usage : python -m app.lancer_collecte_manuelle linkedin \"<mots-clés>\" <lieu>")
                sys.exit(1)
            resultat = scraping_service.run_scraping_and_persist(sys.argv[2], sys.argv[3], limit=5)
        elif source == "lefaso":
            resultat = scraping_service.run_lefaso_and_persist(sys.argv[2])
        elif source == "ici_pe":
            resultat = scraping_service.run_ici_pe_and_persist(sys.argv[2])
        else:
            print(f"Source inconnue : {source} (attendu : linkedin, lefaso ou ici_pe)")
            sys.exit(1)

    for ligne in resultat["logs"]:
        print(ligne)
    print(f"\n{resultat['new_jobs']} nouvelle(s) offre(s) sur {resultat['total_found']} trouvée(s).")


if __name__ == "__main__":
    main()
