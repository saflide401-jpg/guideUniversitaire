# Ce fichier définit toutes les URL accessibles de votre application et la logique d'orchestration

# app/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request # Importe les utilitaires Flask
from flask_login import login_user, current_user, logout_user, login_required # Importe la gestion de session
from app.services import UserService, ScrapingService, AnalyticsService # Importe la couche service (logique métier isolée)
from app.forms import RegistrationForm, LoginForm, RapportForm # Importe les classes de formulaires WTForms
from app.models import Secteur # Importe les modèles nécessaires aux routes

# --- Définition du Blueprint principal ---
# Un Blueprint est un conteneur de routes qui peut être enregistré dans l'application
# "main" est le nom du Blueprint, utilisé pour générer les URL (ex: url_for('main.login'))
main = Blueprint("main", __name__)

# --- Instanciation des services ---
# Le contrôleur ne communique JAMAIS directement avec la base de données
# Il délègue toute la logique métier à ces services (Principe d'Inversion des Dépendances)
user_service = UserService()
scraping_service = ScrapingService()
analytics_service = AnalyticsService()


# === ROUTE : TABLEAU DE BORD (PAGE D'ACCUEIL) ===
@main.route("/") # Accessible via http://localhost:5000/
@main.route("/dashboard") # Accessible aussi via http://localhost:5000/dashboard
@login_required # Décorateur de protection : redirige vers /login si l'utilisateur n'est pas connecté
def dashboard():
    """Affiche le tableau de bord principal avec les indicateurs clés et un aperçu des tendances."""
    kpis = scraping_service.get_dashboard_kpis()
    top_secteurs = analytics_service.get_top_secteurs(limit=5)
    top_competences = analytics_service.get_top_competences(limit=6)
    monthly = analytics_service.get_monthly_volume(months=6)
    recent_jobs = scraping_service.get_recent_jobs(limit=5)
    return render_template(
        "dashboard.html", title="Dashboard", active_page="dashboard",
        kpis=kpis, top_secteurs=top_secteurs, top_competences=top_competences,
        monthly=monthly, recent_jobs=recent_jobs
    )


# === ROUTE : LISTE DES OFFRES COLLECTÉES ===
@main.route("/offres")
@login_required
def offres():
    """Affiche la liste des offres d'emploi collectées, avec filtres optionnels."""
    keyword = request.args.get("keyword", "").strip()
    secteur_id = request.args.get("secteur", type=int)
    location = request.args.get("location", "").strip()

    jobs = scraping_service.get_offres_filtered(
        keyword=keyword or None, secteur_id=secteur_id or None, location=location or None
    )
    secteurs = Secteur.query.order_by(Secteur.nom_secteur).all()

    return render_template(
        "offres.html", title="Offres", active_page="offres",
        jobs=jobs, secteurs=secteurs, keyword=keyword, secteur_id=secteur_id, location=location
    )


# === ROUTE : ANALYSE DES COMPÉTENCES ===
@main.route("/competences")
@login_required
def competences():
    """Affiche les compétences les plus demandées dans les offres collectées."""
    top_competences = analytics_service.get_top_competences(limit=10)
    word_cloud = analytics_service.get_competences_word_cloud(limit=16)
    type_breakdown = analytics_service.get_competence_type_breakdown()
    return render_template(
        "competences.html", title="Compétences", active_page="competences",
        top_competences=top_competences, word_cloud=word_cloud, type_breakdown=type_breakdown
    )


# === ROUTE : TENDANCES DU MARCHÉ ===
@main.route("/tendances")
@login_required
def tendances():
    """Affiche les tendances du marché : répartition sectorielle, volume mensuel, géographie, croissance."""
    donut = analytics_service.get_secteur_repartition_donut(top_n=3)
    monthly = analytics_service.get_monthly_volume(months=24)
    geo = analytics_service.get_geo_distribution(limit=5)
    growth = analytics_service.get_growth_secteurs(limit=4)
    return render_template(
        "tendances.html", title="Tendances", active_page="tendances",
        donut=donut, monthly=monthly, geo=geo, growth=growth
    )


# === ROUTE : RAPPORTS PERSONNALISÉS ===
@main.route("/rapports", methods=["GET", "POST"])
@login_required
def rapports():
    """Permet à l'utilisateur de générer et consulter ses rapports de compétences par secteur."""
    form = RapportForm()
    form.secteur.choices = [(0, "Tous les secteurs")] + [
        (s.id_secteur, s.nom_secteur) for s in Secteur.query.order_by(Secteur.nom_secteur).all()
    ]

    if form.validate_on_submit():
        secteur_id = form.secteur.data or None
        analytics_service.create_rapport(
            user_id=current_user.id,
            titre_rapport=form.titre_rapport.data,
            secteur_id=secteur_id
        )
        flash("Rapport généré avec succès.", "success")
        return redirect(url_for("main.rapports"))

    mes_rapports = analytics_service.get_rapports_for_user(current_user.id)
    return render_template("rapports.html", title="Rapports", active_page="rapports", form=form, rapports=mes_rapports)


# === ROUTE : INSCRIPTION ===
@main.route("/register", methods=["GET", "POST"]) # Accepte les requêtes GET (affichage) et POST (soumission)
def register():
    """Gère l'inscription d'un nouvel utilisateur."""
    # Vérification préalable : si l'utilisateur est déjà connecté, pas besoin de s'inscrire
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard")) # Redirige vers le dashboard

    # Instanciation du formulaire d'inscription (génère aussi le jeton CSRF)
    form = RegistrationForm()

    # validate_on_submit() effectue deux vérifications :
    # 1. La requête est bien un POST (le formulaire a été soumis)
    # 2. Toutes les validations WTForms sont passées (champs obligatoires, longueur, unicité, etc.)
    if form.validate_on_submit():
        # Appel à la couche service pour inscrire l'utilisateur
        # Le contrôleur ne fait PAS le hachage lui-même, il délègue au service
        user, message = user_service.register_user(
            username=form.username.data, # .data contient la valeur saisie par l'utilisateur
            email=form.email.data,
            password=form.password.data
        )
        if user:
            # flash() stocke un message temporaire qui sera affiché sur la page SUIVANTE
            # "success" est la catégorie CSS (affichera un message vert)
            flash(message, "success")
            # Redirige l'utilisateur vers la page de connexion pour qu'il se connecte
            return redirect(url_for("main.login"))
        else:
            # En cas d'échec métier, affiche un message d'erreur rouge
            flash(message, "danger")

    # Rend le template d'inscription en lui transmettant l'objet formulaire
    return render_template("register.html", title="Inscription", form=form)


# === ROUTE : CONNEXION ===
@main.route("/login", methods=["GET", "POST"])
def login():
    """Gère la connexion de l'utilisateur."""
    # Si l'utilisateur est déjà connecté, on le redirige directement vers le dashboard
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    # Instanciation du formulaire de connexion
    form = LoginForm()

    # Si le formulaire est soumis et que toutes les validations sont passées
    if form.validate_on_submit():
        # Demande à la couche service de vérifier les identifiants
        user = user_service.authenticate_user(form.email.data, form.password.data)
        if user:
            # login_user() enregistre l'utilisateur dans la session Flask-Login
            # remember=True : le cookie de session persiste même après fermeture du navigateur
            login_user(user, remember=form.remember.data)

            # Récupère l'URL de la page que l'utilisateur tentait d'atteindre avant d'être redirigé
            next_page = request.args.get("next")

            # Affiche un message de bienvenue vert
            flash("Connexion réussie ! Bienvenue sur Guide Universitaire.", "success")

            # Redirige vers la page demandée à l'origine, ou vers le dashboard par défaut
            return redirect(next_page) if next_page else redirect(url_for("main.dashboard"))
        else:
            # Affiche un message d'erreur rouge si les identifiants sont incorrects
            flash("Échec de la connexion. Veuillez vérifier votre adresse email et votre mot de passe.", "danger")

    # Rend le template de connexion en lui transmettant le formulaire
    return render_template("login.html", title="Connexion", form=form)


# === ROUTE : DÉCONNEXION ===
@main.route("/logout")
def logout():
    """Gère la déconnexion de l'utilisateur."""
    # logout_user() détruit la session utilisateur active (supprime le cookie de session)
    logout_user()
    # Affiche un message d'information bleu confirmant la déconnexion
    flash("Vous avez été déconnecté de votre session.", "info")
    # Redirige vers la page de connexion
    return redirect(url_for("main.login"))
