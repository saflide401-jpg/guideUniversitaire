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
# Le Burkina Faso est volontairement privilégié (7 recherches sur 10 côté LinkedIn, couvrant
# ses secteurs clés : informatique, BTP, mines, agriculture, ONG, microfinance) pour que les
# prochaines collectes reflètent en priorité son marché de l'emploi.
#
# Le site public "Emploi LeFaso.net" est ajouté comme source de diversification
# (source="lefaso"), cette fois centrée sur le Burkina Faso comme LinkedIn : l'objectif est
# d'augmenter le volume d'offres réellement collectées sur cette zone sans dépendre d'un seul
# site (donc d'un seul risque de blocage anti-robot). Facebook et WhatsApp, envisagés un temps
# pour la même raison, ont été explicitement écartés (voir RAPPORT_PROJET.md, section 5.8) :
# le premier interdit le scraping automatisé dans ses conditions d'utilisation, le second
# exposerait les numéros de téléphone et messages de tiers non consentants dans ses groupes.
#
# Une troisième source, le site "ICI Partenaires Entreprises" (source="ici_pe"), a été ajoutée
# après vérification que six autres sites candidats (emploiburkina.com, bfemploi.com,
# afriqueemplois.com, tonjob.net, jooble.org, criburkina.com) étaient soit bloqués (protection
# anti-robot, blocage réseau), soit trop fragiles/incertains pour une collecte fiable — voir
# le détail de cette vérification en section 5.8.
AUTO_SEARCHES = [
    {"source": "linkedin", "keywords": "Développeur Informatique", "location": "Ouagadougou"},
    {"source": "linkedin", "keywords": "Ingénieur Génie Civil", "location": "Ouagadougou"},
    {"source": "linkedin", "keywords": "Comptable", "location": "Bobo-Dioulasso"},
    {"source": "linkedin", "keywords": "Ingénieur des Mines", "location": "Ouagadougou"},
    {"source": "linkedin", "keywords": "Agronome", "location": "Bobo-Dioulasso"},
    {"source": "linkedin", "keywords": "Chargé de projet ONG", "location": "Ouagadougou"},
    {"source": "linkedin", "keywords": "Responsable Microfinance", "location": "Ouagadougou"},
    {"source": "linkedin", "keywords": "Développeur Python", "location": "Paris"},
    {"source": "linkedin", "keywords": "Data Analyst", "location": "Abidjan"},
    {"source": "linkedin", "keywords": "Chef de projet Marketing", "location": "Dakar"},
    {"source": "lefaso", "keywords": "informatique"},
    {"source": "lefaso", "keywords": "comptable"},
    {"source": "lefaso", "keywords": "ingénieur"},
    {"source": "lefaso", "keywords": "communication"},
    {"source": "ici_pe", "keywords": "informatique"},
    {"source": "ici_pe", "keywords": "comptable"},
    {"source": "ici_pe", "keywords": "ingénieur"},
]

_scheduler = None
_search_cycle = itertools.cycle(AUTO_SEARCHES)


def _run_next_auto_collect(app, scraping_service, limit):
    """Exécute une collecte automatique pour la prochaine recherche du cycle."""
    search = next(_search_cycle)
    with app.app_context():
        if search["source"] == "lefaso":
            scraping_service.run_lefaso_and_persist(
                keywords=search["keywords"],
                limit=limit,
            )
        elif search["source"] == "ici_pe":
            scraping_service.run_ici_pe_and_persist(
                keywords=search["keywords"],
                limit=limit,
            )
        else:
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
