# Ce fichier définit toutes les URL accessibles de votre application et la logique d'orchestration

# app/routes.py
import csv
import io
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, abort # Importe les utilitaires Flask
from flask_login import login_user, current_user, logout_user, login_required # Importe la gestion de session
from app.services import UserService, ScrapingService, AnalyticsService # Importe la couche service (logique métier isolée)
from app.forms import RegistrationForm, LoginForm, RapportForm, ForgotPasswordForm, ResetPasswordForm, ProfilForm # Importe les classes de formulaires WTForms
from app.models import Secteur, User, ProfilCandidat # Importe les modèles nécessaires aux routes
from app.nlp.guide_matcher import get_matcher # Rapprochement offre -> guide d'orientation (filières, centres de formation)
from app import db

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
# Accessible sans connexion : un visiteur peut consulter les tendances avant de décider de
# s'inscrire. On invite à se connecter (bandeau + notifications) sans jamais l'imposer.
@main.route("/") # Accessible via http://localhost:5000/
@main.route("/dashboard") # Accessible aussi via http://localhost:5000/dashboard
def dashboard():
    """Affiche le tableau de bord principal avec les indicateurs clés et un aperçu des tendances."""
    kpis = scraping_service.get_dashboard_kpis()
    sparklines = scraping_service.get_kpi_sparklines()
    top_secteurs = analytics_service.get_top_secteurs(limit=5)
    top_competences = analytics_service.get_top_competences(limit=6)
    monthly = analytics_service.get_monthly_volume(months=6)
    recent_jobs = scraping_service.get_recent_jobs(limit=5)
    return render_template(
        "dashboard.html", title="Dashboard", active_page="dashboard",
        kpis=kpis, sparklines=sparklines, top_secteurs=top_secteurs, top_competences=top_competences,
        monthly=monthly, recent_jobs=recent_jobs
    )


# === ROUTE : LISTE DES OFFRES COLLECTÉES ===
@main.route("/offres") # Accessible sans connexion, comme le dashboard
def offres():
    """Affiche la liste des offres d'emploi collectées, avec filtres optionnels."""
    keyword = request.args.get("keyword", "").strip()
    secteur_id = request.args.get("secteur", type=int)
    location = request.args.get("location", "").strip()
    competence = request.args.get("competence", "").strip()

    jobs = scraping_service.get_offres_filtered(
        keyword=keyword or None, secteur_id=secteur_id or None, location=location or None,
        competence=competence or None
    )
    secteurs = Secteur.query.order_by(Secteur.nom_secteur).all()

    return render_template(
        "offres.html", title="Offres", active_page="offres",
        jobs=jobs, secteurs=secteurs, keyword=keyword, secteur_id=secteur_id, location=location,
        competence=competence
    )


# === ROUTE : FICHE DÉTAILLÉE D'UNE OFFRE ===
@main.route("/offres/<int:id_offre>") # Accessible sans connexion, comme la liste des offres
def offre_detail(id_offre):
    """
    Affiche la fiche complète d'une offre, enrichie du rapprochement avec le guide
    d'orientation (filière universitaire et centres de formation permettant d'accéder
    à ce type de poste), déduit du titre de l'offre par correspondance floue.
    """
    job = scraping_service.get_offre_by_id(id_offre)
    if job is None:
        abort(404)

    orientation = get_matcher().matcher(job.titre_poste)

    return render_template(
        "offre_detail.html", title=job.titre_poste, active_page="offres",
        job=job, orientation=orientation
    )


# === ROUTE : ANALYSE DES COMPÉTENCES ===
@main.route("/competences") # Accessible sans connexion, comme le dashboard
def competences():
    """Affiche les compétences les plus demandées dans les offres collectées."""
    top_competences = analytics_service.get_top_competences(limit=10)
    word_cloud = analytics_service.get_competences_word_cloud(limit=16)
    type_breakdown = analytics_service.get_competence_type_breakdown()
    type_donut = analytics_service.get_competence_type_donut()
    kpis = analytics_service.get_competences_kpis()
    return render_template(
        "competences.html", title="Compétences", active_page="competences",
        top_competences=top_competences, word_cloud=word_cloud, type_breakdown=type_breakdown,
        type_donut=type_donut, kpis=kpis
    )


# === ROUTE : OFFRES REQUÉRANT UNE COMPÉTENCE (JSON) ===
@main.route("/competences/<nom_competence>/offres") # Accessible sans connexion, comme la page Compétences
def competence_offres_json(nom_competence):
    """
    Retourne au format JSON les offres actives requérant la compétence donnée, pour permettre
    au nuage de mots-clés (page Compétences) de les afficher immédiatement au clic, sans
    recharger une page complète comme le fait le lien de filtrage classique vers /offres.
    """
    jobs = scraping_service.get_offres_filtered(competence=nom_competence)
    return {
        "competence": nom_competence,
        "total": len(jobs),
        "offres": [
            {
                "id_offre": job.id_offre,
                "titre_poste": job.titre_poste,
                "entreprise": job.entreprise.nom_entreprise,
                "localisation": job.entreprise.localisation or "—",
            }
            for job in jobs
        ],
    }


# === ROUTE : EXPORT CSV DES COMPÉTENCES ===
@main.route("/competences/export.csv") # Accessible sans connexion, cohérent avec la page compétences
def competences_export():
    """Exporte le classement des compétences les plus demandées au format CSV."""
    top_competences = analytics_service.get_top_competences(limit=50)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Compétence", "Occurrences", "Pourcentage du maximum"])
    for c in top_competences:
        writer.writerow([c["nom"], c["total"], f"{c['pourcentage']}%"])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=competences_guide_universitaire.csv"}
    )


# === ROUTE : TENDANCES DU MARCHÉ ===
@main.route("/tendances") # Accessible sans connexion, comme le dashboard
def tendances():
    """Affiche les tendances du marché : répartition sectorielle, volume mensuel, géographie, croissance."""
    donut = analytics_service.get_secteur_repartition_donut(top_n=3)
    monthly = analytics_service.get_monthly_volume(months=24)
    geo = analytics_service.get_geo_distribution(limit=5)
    growth = analytics_service.get_growth_secteurs(limit=4)
    forecast = analytics_service.get_forecast_secteurs(limit=5)
    return render_template(
        "tendances.html", title="Tendances", active_page="tendances",
        donut=donut, monthly=monthly, geo=geo, growth=growth,
        forecast=forecast
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


# === ROUTE : À PROPOS ===
@main.route("/a-propos") # Accessible sans connexion : contenu de présentation
def a_propos():
    """Présente le projet : mission, fonctionnement, technologies utilisées."""
    kpis = scraping_service.get_dashboard_kpis()
    return render_template("about.html", title="À propos", active_page="a_propos", kpis=kpis)


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

            # Première connexion (profil jamais proposé) : invite à compléter son profil avant
            # de continuer, sans jamais l'imposer (l'utilisateur peut passer cette étape).
            if not user.onboarding_vu:
                return redirect(url_for("main.bienvenue", **({"next": next_page} if next_page else {})))

            # Redirige vers la page demandée à l'origine, ou vers le dashboard par défaut
            return redirect(next_page) if next_page else redirect(url_for("main.dashboard"))
        else:
            # Affiche un message d'erreur rouge si les identifiants sont incorrects
            flash("Échec de la connexion. Veuillez vérifier votre adresse email et votre mot de passe.", "danger")

    # Rend le template de connexion en lui transmettant le formulaire
    return render_template("login.html", title="Connexion", form=form)


# === ROUTE : INVITATION À COMPLÉTER SON PROFIL (après connexion, une seule fois) ===
@main.route("/bienvenue", methods=["GET", "POST"])
@login_required
def bienvenue():
    """
    Invite l'utilisateur, juste après sa première connexion, à préciser son niveau de
    compétence et l'emploi qu'il recherche. Purement facultatif : il peut passer cette
    étape via /bienvenue/passer sans que cela ne le bloque nulle part ailleurs.
    """
    next_page = request.args.get("next")
    form = ProfilForm()

    if form.validate_on_submit():
        profil = ProfilCandidat(
            id_user=current_user.id,
            niveau_competence=form.niveau_competence.data,
            emploi_souhaite=form.emploi_souhaite.data,
            competences_actuelles=form.competences_actuelles.data
        )
        db.session.add(profil)
        current_user.onboarding_vu = True
        db.session.commit()
        flash("Merci ! Votre profil a été enregistré.", "success")
        return redirect(next_page) if next_page else redirect(url_for("main.dashboard"))

    return render_template("bienvenue.html", title="Bienvenue", form=form, next_page=next_page)


# === ROUTE : PASSER L'INVITATION AU PROFIL ===
@main.route("/bienvenue/passer")
@login_required
def bienvenue_passer():
    """Marque l'invitation comme vue sans enregistrer de profil : l'utilisateur ne sera plus sollicité."""
    current_user.onboarding_vu = True
    db.session.commit()
    next_page = request.args.get("next")
    return redirect(next_page) if next_page else redirect(url_for("main.dashboard"))


# === ROUTE : MOT DE PASSE OUBLIÉ ===
@main.route("/mot-de-passe-oublie", methods=["GET", "POST"])
def forgot_password():
    """Demande de réinitialisation : envoie un e-mail contenant un lien à durée limitée."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = user_service.generate_reset_token(user)
            user_service.send_reset_email(user, token)

        # Message volontairement identique que l'email existe ou non : cela évite de révéler
        # à un attaquant quelles adresses sont associées à un compte existant.
        flash("Si un compte existe avec cette adresse, un e-mail de réinitialisation vient d'être envoyé.", "success")
        return redirect(url_for("main.login"))

    return render_template("forgot_password.html", title="Mot de passe oublié", form=form)


# === ROUTE : RÉINITIALISATION DU MOT DE PASSE ===
@main.route("/reinitialiser-mot-de-passe/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Vérifie le jeton reçu par e-mail et permet de définir un nouveau mot de passe."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    user = user_service.verify_reset_token(token)
    if not user:
        flash("Ce lien de réinitialisation est invalide ou a expiré. Veuillez refaire une demande.", "danger")
        return redirect(url_for("main.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user_service.update_password(user, form.password.data)
        flash("Votre mot de passe a été réinitialisé avec succès. Vous pouvez vous connecter.", "success")
        return redirect(url_for("main.login"))

    return render_template("reset_password.html", title="Nouveau mot de passe", form=form)


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
