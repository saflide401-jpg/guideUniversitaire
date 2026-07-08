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