# Ce fichier pilote la collecte automatique des offres d'emploi, en tâche de fond,
# sans aucune action requise de la part de l'utilisateur.
# La collecte est planifiée à des jours et heures fixes chaque semaine (cron hebdomadaire),
# et non plus à intervalle régulier : cela garantit un rythme prévisible d'actualisation
# des données affichées sur le tableau de bord et les pages d'analyse.

import os
import itertools
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# --- Rotation des recherches couvrant plusieurs secteurs et villes ---
# À chaque exécution planifiée, une seule recherche de la liste est lancée (round-robin),
# afin de répartir la charge dans le temps et de limiter le risque de blocage LinkedIn.
# Le Burkina Faso est volontairement privilégié (7 recherches sur 10, couvrant ses secteurs
# clés : informatique, BTP, mines, agriculture, ONG, microfinance) pour que les prochaines
# collectes reflètent en priorité son marché de l'emploi. Quelques recherches hors Burkina Faso
# sont conservées pour garder un point de comparaison régional.
AUTO_SEARCHES = [
    {"keywords": "Développeur Informatique", "location": "Ouagadougou"},
    {"keywords": "Ingénieur Génie Civil", "location": "Ouagadougou"},
    {"keywords": "Comptable", "location": "Bobo-Dioulasso"},
    {"keywords": "Ingénieur des Mines", "location": "Ouagadougou"},
    {"keywords": "Agronome", "location": "Bobo-Dioulasso"},
    {"keywords": "Chargé de projet ONG", "location": "Ouagadougou"},
    {"keywords": "Responsable Microfinance", "location": "Ouagadougou"},
    {"keywords": "Développeur Python", "location": "Paris"},
    {"keywords": "Data Analyst", "location": "Abidjan"},
    {"keywords": "Chef de projet Marketing", "location": "Dakar"},
]

_scheduler = None
_search_cycle = itertools.cycle(AUTO_SEARCHES)


def _run_next_auto_collect(app, scraping_service, limit):
    """Exécute une collecte automatique pour la prochaine recherche du cycle."""
    search = next(_search_cycle)
    with app.app_context():
        scraping_service.run_scraping_and_persist(
            keywords=search["keywords"],
            location=search["location"],
            limit=limit,
        )


def start_auto_scraping(app, scraping_service):
    """
    Démarre le planificateur de collecte automatique en arrière-plan.

    La collecte n'est jamais déclenchée par l'utilisateur : elle s'exécute à des
    jours et heures fixes chaque semaine (par défaut lundi/mercredi/vendredi à 2h),
    afin que les tableaux de bord et pages d'analyse restent à jour en continu.
    """
    global _scheduler

    if not app.config.get("AUTO_SCRAPING_ENABLED", True):
        return

    # Avec le rechargeur de Flask (debug=True), le processus est dupliqué : on ne démarre
    # le planificateur que dans le process principal pour éviter les collectes en double.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    if _scheduler is not None:
        return

    days = app.config.get("AUTO_SCRAPING_DAYS", "mon,wed,fri")
    hour = app.config.get("AUTO_SCRAPING_HOUR", 2)
    minute = app.config.get("AUTO_SCRAPING_MINUTE", 0)
    limit = app.config.get("AUTO_SCRAPING_LIMIT", 10)

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        func=lambda: _run_next_auto_collect(app, scraping_service, limit),
        trigger=CronTrigger(day_of_week=days, hour=hour, minute=minute),
        id="auto_scraping_job",
        replace_existing=True,
    )
    _scheduler.start()
