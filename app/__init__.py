#app/__init__.py
#Ce fichier est le point d'entrée du package Python app. Lorsque Python importe le package app, c'est ce fichier qui est exécuté en premie

from flask import Flask # Importe la classe principale du framework Flask
from flask_sqlalchemy import SQLAlchemy # Importe l'ORM pour la communication avec PostgreSQL
from flask_bcrypt import Bcrypt # Importe l'outil de hachage sécurisé des mots de passe
from flask_login import LoginManager # Importe le gestionnaire de sessions utilisateur
from flask_mail import Mail # Importe l'envoi d'e-mails (réinitialisation de mot de passe)
from config import Config # Importe la classe de configuration centralisée (config.py)

# --- Instanciation des extensions de manière globale mais NON liée à l'application ---
# Ce découplage est nécessaire pour appliquer le pattern Application Factory
# Les extensions sont créées "vides" ici, puis liées à l'application dans create_app()
db = SQLAlchemy() # Objet de base de données (sera lié à PostgreSQL plus tard)
bcrypt = Bcrypt() # Objet de chiffrement (sera utilisé pour hacher les mots de passe)
login_manager = LoginManager() # Objet de gestion des sessions
mail = Mail() # Objet d'envoi d'e-mails

# --- Configuration globale du gestionnaire de sessions Flask-Login ---
# login_view : nom de la route vers laquelle Flask-Login redirige si un utilisateur non connecté
#              tente d'accéder à une page protégée par @login_required
login_manager.login_view = 'main.login'
# login_message : message d'avertissement affiché lors de la redirection forcée
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
# login_message_category : classe CSS Bootstrap appliquée au message (ici 'info' = style bleu)
login_manager.login_message_category = 'info'


def create_app(config_class=Config):
    """
    Fabrique d'application (Application Factory Pattern).
    Cette fonction crée, configure et retourne une nouvelle instance de l'application Flask.
    
    Args:
        config_class : La classe de configuration à utiliser (par défaut : Config)
    """
    app = Flask(__name__) # Crée l'instance de l'application Flask
    app.config.from_object(config_class) # Charge les paramètres depuis la classe de configuration

    # --- Liaison dynamique des extensions à l'instance de l'application ---
    # init_app() connecte chaque extension à cette instance spécifique de Flask
    db.init_app(app) # Connecte SQLAlchemy à l'application
    bcrypt.init_app(app) # Connecte Bcrypt à l'application
    login_manager.init_app(app) # Connecte le gestionnaire de sessions à l'application
    mail.init_app(app) # Connecte l'envoi d'e-mails à l'application

    # --- Importation locale des modèles ---
    # L'import est fait ICI (à l'intérieur de la fonction) pour éviter les importations circulaires
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        """
        Fonction de rappel (callback) appelée automatiquement par Flask-Login à chaque requête HTTP.
        Elle charge l'utilisateur connecté à partir de l'ID stocké dans le cookie de session.
        Cette fonction est placée ici pour respecter le SRP (gestion de session dans __init__.py).
        """
        return User.query.get(int(user_id))

    # --- Enregistrement des Blueprints (Contrôleurs) ---
    # Les Blueprints permettent de découper l'application en modules indépendants
    from app.routes import main as main_bp, scraping_service
    app.register_blueprint(main_bp) # Enregistre le Blueprint 'main' dans l'application

    # --- Démarrage de la collecte automatique en arrière-plan ---
    # La collecte des offres n'est jamais déclenchée manuellement par l'utilisateur :
    # elle tourne en continu selon un intervalle défini, pour que les tableaux de bord
    # et pages d'analyse restent à jour en temps réel.
    from app.scheduler import start_auto_scraping
    start_auto_scraping(app, scraping_service)

    return app # Retourne l'application Flask entièrement configurée et prête à être lancée