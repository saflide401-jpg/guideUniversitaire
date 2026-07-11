# Ce fichier déclare les formulaires de l'application avec leurs champs et leurs règles de validation

# app/forms.py
from flask_wtf import FlaskForm # Importe la classe de base des formulaires Flask (inclut la protection CSRF)
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, TextAreaField # Importe les types de champs
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError # Importe les validateurs
from app.models import User # Importe le modèle User pour les validations d'unicité


class RegistrationForm(FlaskForm):
    """
    Formulaire d'inscription d'un nouvel utilisateur.
    Hérite de FlaskForm qui ajoute automatiquement un champ caché CSRF pour la sécurité.
    """
    
    # Champ texte pour le nom d'utilisateur
    # validators est une liste de règles que le champ doit respecter pour être valide
    username = StringField(
        "Nom d'utilisateur", # Label affiché dans le HTML
        validators=[
            DataRequired(message="Ce champ est obligatoire."), # Le champ ne peut pas être vide
            Length(min=2, max=20, message="Le nom d'utilisateur doit contenir entre 2 et 20 caractères.")
        ]
    )
    
    # Champ texte pour l'adresse email avec validation de format
    email = StringField(
        "Adresse Email", 
        validators=[
            DataRequired(message="Ce champ est obligatoire."), 
            Email(message="Veuillez saisir une adresse email valide.") # Vérifie la présence du @ et du domaine
        ]
    )
    
    # Champ mot de passe masqué (les caractères sont remplacés par des points)
    password = PasswordField(
        "Mot de passe", 
        validators=[
            DataRequired(message="Ce champ est obligatoire."),
            Length(min=6, message="Le mot de passe doit contenir au moins 6 caractères.")
        ]
    )
    
    # Champ de confirmation : doit être identique au champ 'password'
    confirm_password = PasswordField(
        "Confirmer le mot de passe", 
        validators=[
            DataRequired(message="Ce champ est obligatoire."), 
            EqualTo("password", message="Les mots de passe ne correspondent pas.") # Compare avec le champ 'password'
        ]
    )
    
    # Bouton de soumission du formulaire
    submit = SubmitField("Créer mon compte")

    # --- Validations personnalisées ---
    # WTForms appelle automatiquement toute méthode nommée validate_<nom_du_champ>()
    # Si la validation échoue, on lève une ValidationError qui sera affichée à l'utilisateur
    
    def validate_username(self, username):
        """Vérifie que le nom d'utilisateur n'existe pas déjà en base de données."""
        user = User.query.filter_by(username=username.data).first() # .data contient la valeur saisie
        if user:
            raise ValidationError("Ce nom d'utilisateur est déjà pris. Veuillez en choisir un autre.")

    def validate_email(self, email):
        """Vérifie que l'email n'existe pas déjà en base de données."""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError("Cette adresse email est déjà associée à un compte.")


class LoginForm(FlaskForm):
    """
    Formulaire de connexion de l'utilisateur.
    Plus simple que le formulaire d'inscription car il ne nécessite pas de validation d'unicité.
    """
    
    # Champ email obligatoire avec validation de format
    email = StringField(
        "Adresse Email", 
        validators=[
            DataRequired(message="Ce champ est obligatoire."), 
            Email(message="Veuillez saisir une adresse email valide.")
        ]
    )
    
    # Champ mot de passe masqué obligatoire
    password = PasswordField(
        "Mot de passe", 
        validators=[
            DataRequired(message="Ce champ est obligatoire.")
        ]
    )
    
    # Case à cocher pour maintenir la session active même après fermeture du navigateur
    remember = BooleanField("Se souvenir de moi")
    
    # Bouton de soumission
    submit = SubmitField("Se connecter")

class ForgotPasswordForm(FlaskForm):
    """Formulaire de demande de réinitialisation de mot de passe (saisie de l'email)."""
    email = StringField(
        "Adresse Email",
        validators=[
            DataRequired(message="Ce champ est obligatoire."),
            Email(message="Veuillez saisir une adresse email valide.")
        ]
    )
    submit = SubmitField("Envoyer le lien de réinitialisation")


class ResetPasswordForm(FlaskForm):
    """Formulaire de saisie du nouveau mot de passe, utilisé via un lien de réinitialisation."""
    password = PasswordField(
        "Nouveau mot de passe",
        validators=[
            DataRequired(message="Ce champ est obligatoire."),
            Length(min=6, message="Le mot de passe doit contenir au moins 6 caractères.")
        ]
    )
    confirm_password = PasswordField(
        "Confirmer le mot de passe",
        validators=[
            DataRequired(message="Ce champ est obligatoire."),
            EqualTo("password", message="Les mots de passe ne correspondent pas.")
        ]
    )
    submit = SubmitField("Réinitialiser le mot de passe")


class ProfilForm(FlaskForm):
    """
    Formulaire d'invitation (facultatif) proposé une seule fois après la connexion :
    statut en compétences et emploi souhaité. Sert uniquement à enrichir le profil de
    l'utilisateur en base ; aucune donnée n'est traitée automatiquement pour le moment.
    """
    niveau_competence = SelectField(
        "Votre niveau actuel",
        choices=[
            ("Débutant", "Débutant"),
            ("Intermédiaire", "Intermédiaire"),
            ("Avancé", "Avancé"),
            ("Expert", "Expert"),
        ],
        validators=[DataRequired(message="Veuillez sélectionner votre niveau.")]
    )
    emploi_souhaite = StringField(
        "Emploi souhaité",
        validators=[
            DataRequired(message="Veuillez indiquer l'emploi que vous recherchez."),
            Length(max=255)
        ]
    )
    competences_actuelles = TextAreaField(
        "Vos compétences actuelles (facultatif)",
        validators=[Length(max=2000)]
    )
    submit = SubmitField("Enregistrer mon profil")


class RapportForm(FlaskForm):
    """
    Formulaire permettant de générer un rapport personnalisé de compétences,
    ciblé sur un secteur d'activité (ou sur l'ensemble des offres collectées).
    """
    titre_rapport = StringField(
        "Titre du rapport",
        validators=[
            DataRequired(message="Veuillez donner un titre à votre rapport."),
            Length(max=255)
        ]
    )
    secteur = SelectField(
        "Secteur ciblé",
        coerce=int
    )
    submit = SubmitField("Générer le rapport")