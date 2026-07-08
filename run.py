# Ce fichier est le point d'entrée de votre application


from app import create_app, db # Importe la fabrique d'application et l'objet de base de données
import click # Importe l'outil de création d'interfaces en ligne de commande (CLI)

# Crée l'instance de l'application Flask en appelant notre fabrique (Factory Method)
# Cette ligne exécute create_app() qui initialise toutes les extensions et enregistre les routes
app = create_app()

# Définit une commande CLI personnalisée accessible via : flask init-db
@app.cli.command("init-db")
def init_db():
    """Crée toutes les tables de la base de données PostgreSQL."""
    # create_all() parcourt tous les modèles SQLAlchemy importés (User, Secteur, Entreprise, etc.)
    # et génère les instructions SQL CREATE TABLE correspondantes dans PostgreSQL
    db.create_all()
    # Affiche un message de confirmation dans la console
    click.echo("Base de données initialisée avec succès !")

# Si le script est exécuté directement (ex: python run.py)
if __name__ == "__main__":
    # Démarre le serveur de développement Flask
    # host="0.0.0.0" : écoute sur toutes les interfaces réseau (nécessaire pour Docker)
    # port=5000 : le serveur sera accessible sur http://localhost:5000
    # debug=True : active le rechargement automatique du code et affiche les erreurs détaillées
    app.run(host="0.0.0.0", port=5000, debug=True )