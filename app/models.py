# Ce fichier définit la structure de toutes les tables de la base de données

# linkedin_recruitment_trends/app/models.py
from app import db # Importe l'objet de base de données SQLAlchemy créé dans __init__.py
from datetime import datetime # Importe le module pour gérer les dates et heures automatiques
from flask_login import UserMixin # Importe la classe de base qui fournit les méthodes standard de session

# Note de conception : Le chargeur d'utilisateur (user_loader) a été déplacé dans app/__init__.py
# pour respecter le Principe de Responsabilité Unique (SRP) et éviter les importations circulaires.


class Secteur(db.Model):
    """
    Représente un secteur d'activité (ex: Informatique, Finance, Santé).
    Correspond à la table 'secteur' dans PostgreSQL.
    """
    __tablename__ = 'secteur' # Définit le nom exact de la table dans PostgreSQL
    
    id_secteur = db.Column(db.Integer, primary_key=True) # Clé primaire auto-incrémentée
    nom_secteur = db.Column(db.String(150), nullable=False, unique=True) # Nom unique et obligatoire
    
    # Relations virtuelles SQLAlchemy (ne créent pas de colonnes physiques en base)
    # backref='secteur' crée automatiquement un attribut 'secteur' dans le modèle Entreprise
    # lazy=True signifie que les données associées ne sont chargées que lorsqu'on y accède (Lazy Loading)
    entreprises = db.relationship('Entreprise', backref='secteur', lazy=True)
    offres_emploi = db.relationship('OffreEmploi', backref='secteur', lazy=True)
    rapports_personnalises = db.relationship('RapportPersonnalise', backref='secteur', lazy=True)


class Entreprise(db.Model):
    """
    Représente une entreprise qui recrute (ex: Google, Société Générale).
    Correspond à la table 'entreprise' dans PostgreSQL.
    """
    __tablename__ = 'entreprise' # Définit le nom exact de la table dans PostgreSQL
    
    id_entreprise = db.Column(db.Integer, primary_key=True) # Clé primaire auto-incrémentée
    nom_entreprise = db.Column(db.String(255), nullable=False, unique=True) # Nom unique et obligatoire
    localisation = db.Column(db.String(255)) # Localisation géographique (champ optionnel)
    
    # Clé étrangère : crée un lien physique vers la clé primaire de la table 'secteur'
    # nullable=False signifie que chaque entreprise DOIT appartenir à un secteur
    id_secteur = db.Column(db.Integer, db.ForeignKey('secteur.id_secteur'), nullable=False)
    
    # Relation virtuelle : une entreprise publie plusieurs offres d'emploi
    offres_emploi = db.relationship('OffreEmploi', backref='entreprise', lazy=True)


class OffreEmploi(db.Model):
    """
    Représente une offre d'emploi scrapée depuis LinkedIn.
    Correspond à la table 'offre_emploi' dans PostgreSQL.
    C'est la table centrale de notre application.
    """
    __tablename__ = 'offre_emploi' # Définit le nom exact de la table dans PostgreSQL
    
    id_offre = db.Column(db.Integer, primary_key=True) # Clé primaire auto-incrémentée
    linkedin_job_id = db.Column(db.String(100), unique=True) # ID unique LinkedIn pour éviter les doublons lors du scraping
    titre_poste = db.Column(db.String(255), nullable=False) # Titre de l'offre (ex: "Développeur Python Senior")
    description = db.Column(db.Text) # Description complète de l'offre (champ texte de longueur illimitée)
    date_publication = db.Column(db.Date) # Date de publication originale sur LinkedIn
    date_scraping = db.Column(db.DateTime, nullable=False, default=datetime.now) # Date/heure d'extraction automatique
    
    # Clés étrangères associant l'offre à une entreprise et un secteur
    id_entreprise = db.Column(db.Integer, db.ForeignKey('entreprise.id_entreprise'), nullable=False)
    id_secteur = db.Column(db.Integer, db.ForeignKey('secteur.id_secteur'), nullable=False)
    
    # Relation plusieurs-à-plusieurs (Many-to-Many) avec les compétences
    # secondary='offre_competence' indique la table pivot qui fait le lien physique
    competences = db.relationship('Competence', secondary='offre_competence', backref='offres_emploi', lazy=True)


class Competence(db.Model):
    """
    Représente une compétence technique ou humaine (ex: Python, Management, SQL).
    Correspond à la table 'competence' dans PostgreSQL.
    """
    __tablename__ = 'competence' # Définit le nom exact de la table dans PostgreSQL
    
    id_competence = db.Column(db.Integer, primary_key=True) # Clé primaire auto-incrémentée
    nom_competence = db.Column(db.String(200), nullable=False, unique=True) # Nom unique (ex: "Python")
    type_competence = db.Column(db.String(100)) # Catégorie (ex: "Hard Skill" ou "Soft Skill")


class OffreCompetence(db.Model):
    """
    Table d'association (table pivot) entre les Offres d'Emploi et les Compétences.
    Elle matérialise la relation Many-to-Many entre ces deux entités.
    Correspond à la table 'offre_competence' dans PostgreSQL.
    """
    __tablename__ = 'offre_competence' # Définit le nom exact de la table dans PostgreSQL
    
    # Clés primaires composites : la combinaison (id_offre, id_competence) est unique
    id_offre = db.Column(db.Integer, db.ForeignKey('offre_emploi.id_offre'), primary_key=True)
    id_competence = db.Column(db.Integer, db.ForeignKey('competence.id_competence'), primary_key=True)


class User(db.Model, UserMixin):
    """
    Représente un utilisateur de l'application (Étudiant, Professionnel).
    Correspond à la table 'user' dans PostgreSQL.
    Hérite de UserMixin qui fournit automatiquement les propriétés requises par Flask-Login.
    """
    __tablename__ = 'user' # Définit le nom exact de la table dans PostgreSQL
    
    id = db.Column(db.Integer, primary_key=True) # Clé primaire (nommée 'id' pour compatibilité Flask-Login)
    username = db.Column(db.String(150), nullable=False, unique=True) # Nom d'utilisateur unique et obligatoire
    email = db.Column(db.String(255), nullable=False, unique=True) # Email unique et obligatoire
    password = db.Column(db.String(255), nullable=False) # Mot de passe haché stocké de manière sécurisée
    date_inscription = db.Column(db.DateTime, nullable=False, default=datetime.now) # Date d'inscription automatique
    # Indique si l'invitation à compléter le profil (compétences/emploi souhaité) a déjà été
    # présentée à l'utilisateur, qu'il l'ait remplie ou volontairement ignorée — pour ne la
    # proposer qu'une seule fois après l'inscription, jamais imposer.
    onboarding_vu = db.Column(db.Boolean, nullable=False, default=False)

    # Relation virtuelle : un utilisateur peut générer plusieurs rapports personnalisés
    rapports_personnalises = db.relationship('RapportPersonnalise', backref='user', lazy=True)
    # Relation virtuelle : profil candidat optionnel (un seul par utilisateur)
    profil_candidat = db.relationship('ProfilCandidat', backref='user', uselist=False, lazy=True)

    def get_id(self):
        """Surcharge de la méthode de UserMixin pour retourner l'ID sous forme de chaîne."""
        # Flask-Login exige que get_id() retourne une chaîne de caractères (str), pas un entier
        return str(self.id)


class ProfilCandidat(db.Model):
    """
    Profil optionnel rempli après connexion : statut en termes de compétences et emploi
    souhaité. Purement déclaratif pour le moment — conservé en base sans traitement
    automatique ni recommandation, en vue d'une personnalisation future.
    """
    __tablename__ = 'profil_candidat'

    id_profil = db.Column(db.Integer, primary_key=True)
    id_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    niveau_competence = db.Column(db.String(50), nullable=False) # Débutant / Intermédiaire / Avancé / Expert
    emploi_souhaite = db.Column(db.String(255), nullable=False) # Ex: "Data Analyst"
    competences_actuelles = db.Column(db.Text) # Compétences déclarées par l'utilisateur, texte libre
    date_creation = db.Column(db.DateTime, nullable=False, default=datetime.now)


class RapportPersonnalise(db.Model):
    """
    Représente un rapport d'analyse personnalisé généré par un utilisateur.
    Correspond à la table 'rapport_personnalise' dans PostgreSQL.
    """
    __tablename__ = 'rapport_personnalise' # Définit le nom exact de la table dans PostgreSQL
    
    id_rapport = db.Column(db.Integer, primary_key=True) # Clé primaire auto-incrémentée
    titre_rapport = db.Column(db.String(255), nullable=False) # Titre du rapport (ex: "Tendances Python 2024")
    competences_recherchees = db.Column(db.Text) # Compétences ciblées par l'utilisateur (format texte libre)
    date_creation = db.Column(db.DateTime, nullable=False, default=datetime.now) # Date de création automatique
    
    # Clés étrangères associant le rapport à un utilisateur et optionnellement à un secteur
    id_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # L'auteur du rapport (obligatoire)
    id_secteur = db.Column(db.Integer, db.ForeignKey('secteur.id_secteur'), nullable=True) # Secteur ciblé (optionnel)