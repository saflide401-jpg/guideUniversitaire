# GUIDE UNIVERSITAIRE/config.py
import os # Importe le module système pour lire les variables d'environnement
from dotenv import load_dotenv # Importe la fonction pour charger le fichier .env

# ChargeR les variables d'environnement depuis le fichier .env
load_dotenv()

class Config:
    """Classe de configuration centralisée de l'application."""
    
    # Clé secrète indispensable pour signer les cookies de session et sécuriser les formulaires CSRF
    # Récupérée depuis les variables d'environnement ou valeur par défaut si absente
    SECRET_KEY = os.environ.get("SECRET_KEY")    
    # URL de connexion à la base de données PostgreSQL
    # Format : postgresql://utilisateur:mot_de_passe@hote:port/nom_base
    # Récupérée depuis les variables d'environnement ou valeur par défaut (PostgreSQL local)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")    
    # Désactive le système de notification d'événements de SQLAlchemy pour économiser les ressources de la machine
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Collecte automatique des offres (aucune action utilisateur requise) ---
    # Active/désactive le planificateur de collecte en arrière-plan
    AUTO_SCRAPING_ENABLED = os.environ.get("AUTO_SCRAPING_ENABLED", "true").lower() != "false"
    # Jours de la semaine où la collecte automatique est déclenchée (format cron APScheduler)
    AUTO_SCRAPING_DAYS = os.environ.get("AUTO_SCRAPING_DAYS", "mon,wed,fri")
    # Heure et minute de déclenchement les jours planifiés
    AUTO_SCRAPING_HOUR = int(os.environ.get("AUTO_SCRAPING_HOUR", 2))
    AUTO_SCRAPING_MINUTE = int(os.environ.get("AUTO_SCRAPING_MINUTE", 0))
    # Nombre maximum d'offres récupérées à chaque collecte automatique
    AUTO_SCRAPING_LIMIT = int(os.environ.get("AUTO_SCRAPING_LIMIT", 10))

    # --- Envoi d'e-mails (réinitialisation de mot de passe) ---
    # Si MAIL_USERNAME n'est pas défini, l'e-mail n'est pas réellement envoyé : le lien de
    # réinitialisation est journalisé côté serveur à la place, pour rester testable en local
    # sans exiger de vrai compte SMTP.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() != "false"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME)
    # Durée de validité du lien de réinitialisation, en secondes (30 minutes par défaut)
    RESET_TOKEN_MAX_AGE = int(os.environ.get("RESET_TOKEN_MAX_AGE", 1800))

    # --- API officielle France Travail (source complémentaire au scraping LinkedIn) ---
    # Facultatifs : si absents, ScrapingService.france_travail_client reste à None et
    # run_france_travail_and_persist se contente de le signaler dans ses logs.
    # Obtention : créer un compte développeur gratuit sur https://francetravail.io,
    # créer une application, puis s'abonner à l'API "Offres d'emploi v2".
    FRANCE_TRAVAIL_CLIENT_ID = os.environ.get("FRANCE_TRAVAIL_CLIENT_ID")
    FRANCE_TRAVAIL_CLIENT_SECRET = os.environ.get("FRANCE_TRAVAIL_CLIENT_SECRET")

if not Config.SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY manquante. Définissez-la dans votre fichier .env "
            "ou dans les variables d'environnement de docker-compose.yml."
        )
if not Config.SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            "DATABASE_URL manquante. Définissez-la dans votre fichier .env "
            "ou dans les variables d'environnement de docker-compose.yml."
        )