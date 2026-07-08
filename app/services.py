# Ce fichier contient toute la logique métier : comptes utilisateurs, scraping et persistance des offres

from app.models import Secteur, Entreprise, OffreEmploi, Competence, OffreCompetence, User, RapportPersonnalise # Importe les modèles de données
from app.scraping.scraper import LinkedInScraper # Importe le scraper Selenium
from app import db, bcrypt # Importe l'instance SQLAlchemy et l'outil de chiffrement Bcrypt
from datetime import datetime, timedelta # Pour gérer les dates
from sqlalchemy import func, extract # Pour les agrégations SQL (comptages, regroupements par mois)
from math import pi # Pour calculer la circonférence des graphiques en anneau (donut)

class UserService:
    """
    Service encapsulant toute la logique métier liée aux utilisateurs.
    Ce service est appelé par les contrôleurs (routes) et interagit avec les modèles.
    Il applique le Principe de Responsabilité Unique (SRP) : sa seule responsabilité
    est de gérer les opérations liées aux comptes utilisateurs.
    """
    
    def register_user(self, username, email, password):
        """
        Inscrit un nouvel utilisateur après validation des contraintes métier.
        
        Args:
            username (str) : Le nom d'utilisateur unique choisi par l'utilisateur.
            email (str) : L'adresse email unique de l'utilisateur.
            password (str) : Le mot de passe en clair saisi par l'utilisateur.
            
        Returns:
            tuple: (User, str) - L'utilisateur créé (ou None en cas d'échec) et un message de statut.
        """
        # Règle métier 1 : L'email doit être unique dans la base de données
        # filter_by(email=email) génère : SELECT * FROM user WHERE email = 'email' LIMIT 1
        # .first() retourne le premier résultat ou None si aucun résultat
        if User.query.filter_by(email=email).first():
            return None, "Cette adresse email est déjà associée à un compte."
            
        # Règle métier 2 : Le nom d'utilisateur doit être unique
        if User.query.filter_by(username=username).first():
            return None, "Ce nom d'utilisateur est déjà pris. Veuillez en choisir un autre."
            
        # Règle de sécurité : Chiffrement irréversible du mot de passe avec Bcrypt
        # generate_password_hash() applique l'algorithme Bcrypt qui :
        #   1. Génère un sel (salt) aléatoire unique pour chaque mot de passe
        #   2. Combine le sel avec le mot de passe et applique un hachage cryptographique
        #   3. Le résultat est irréversible : impossible de retrouver le mot de passe original
        # decode('utf-8') convertit le résultat binaire en chaîne de caractères pour le stockage en base
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # Création d'une nouvelle instance du modèle User avec les données validées
        new_user = User(username=username, email=email, password=hashed_password)
        
        try:
            # Ajoute le nouvel utilisateur à la transaction en cours (pas encore enregistré physiquement)
            db.session.add(new_user)
            # Valide la transaction : enregistre physiquement l'utilisateur dans PostgreSQL
            db.session.commit()
            return new_user, "Votre compte a été créé avec succès ! Vous pouvez maintenant vous connecter."
        except Exception as e:
            # En cas d'erreur (ex: violation de contrainte unique), annule toute la transaction
            # Le rollback garantit que la base de données reste dans un état cohérent
            db.session.rollback()
            return None, "Une erreur technique est survenue lors de l'inscription. Veuillez réessayer."

    def authenticate_user(self, email, password):
        """
        Valide les identifiants de connexion d'un utilisateur.
        
        Args:
            email (str) : L'email saisi dans le formulaire de connexion.
            password (str) : Le mot de passe en clair saisi dans le formulaire.
            
        Returns:
            User: L'objet utilisateur si l'authentification réussit, sinon None.
        """
        # Recherche l'utilisateur par son email dans la base de données
        # Génère : SELECT * FROM user WHERE email = 'email' LIMIT 1
        user = User.query.filter_by(email=email).first()
        
        # Vérifie deux conditions :
        # 1. L'utilisateur existe bien en base (user n'est pas None)
        # 2. Le mot de passe saisi correspond au hachage stocké
        # check_password_hash() refait le calcul Bcrypt avec le même sel et compare les résultats
        if user and bcrypt.check_password_hash(user.password, password):
            return user # Authentification réussie : retourne l'objet utilisateur complet
            
        return None # Authentification échouée : email inexistant ou mot de passe incorrect
    

    #  (Suite - ScrapingService)


class ScrapingService:
    """
    Service responsable du nettoyage, de l'analyse et de la persistance des offres d'emploi.
    Il applique le Principe de Responsabilité Unique (SRP) : sa seule mission est de
    prendre des données brutes, de les structurer et de les insérer proprement en base.
    """
    
    def __init__(self):
        """Initialise le scraper et le dictionnaire des compétences connues."""
        self.scraper = LinkedInScraper()
        
        # --- Dictionnaire de compétences de référence ---
        # Utilisé pour analyser la description textuelle des offres d'emploi.
        # Clé : Nom de la compétence (sera inséré en base)
        # Valeur : Liste des mots-clés à chercher dans le texte (insensible à la casse)
        self.skills_dictionary = {
            "Python": ["python", "py"],
            "Java": ["java", "jee"],
            "JavaScript": ["javascript", "js", "node", "nodejs"],
            "SQL": ["sql", "postgresql", "mysql", "oracle"],
            "Docker": ["docker", "container", "kubernetes"],
            "HTML/CSS": ["html", "css", "bootstrap", "tailwind"],
            "Git": ["git", "github", "gitlab"],
            "Scrum/Agile": ["scrum", "agile", "kanban"],
            "Anglais": ["anglais", "english"],
            "Communication": ["communication", "relationnel", "équipe"]
        }

    def run_scraping_and_persist(self, keywords, location, limit=5):
        """
        Lance le scraping, analyse les offres, détecte les compétences et enregistre en base.

        Args:
            keywords (str) : Les mots-clés de recherche (ex: "Data Scientist")
            location (str) : La localisation (ex: "Dakar")
            limit (int) : Le nombre maximum d'offres à traiter

        Returns:
            dict : {"new_jobs": int, "total_found": int, "logs": list[str]} résumant l'exécution.
        """
        # 1. Appel au scraper Selenium pour récupérer les données brutes du web
        raw_jobs = self.scraper.scrape_jobs(keywords, location, limit)
        new_jobs_count = 0
        logs = [f"Recherche \"{keywords}\" à \"{location}\" : {len(raw_jobs)} offre(s) trouvée(s)."]

        # 2. Traitement et persistance de chaque offre de manière transactionnelle
        for raw_job in raw_jobs:
            try:
                # --- RÈGLE MÉTIER 1 : Éviter les doublons d'offres d'emploi ---
                # On vérifie si l'offre existe déjà en base via son ID unique LinkedIn
                existing_job = OffreEmploi.query.filter_by(linkedin_job_id=raw_job["linkedin_job_id"]).first()
                if existing_job:
                    logs.append(f"Offre déjà connue ignorée : {raw_job['titre_poste']}")
                    continue # Ignore l'offre et passe à la suivante
                
                # --- RÈGLE MÉTIER 2 : Gérer le Secteur d'activité ---
                # Pour ce jalon, nous associons les offres à un secteur par défaut basé sur le mot-clé de recherche
                # On cherche si le secteur existe déjà en base, sinon on le crée (idempotence)
                secteur_nom = keywords.capitalize()
                secteur = Secteur.query.filter_by(nom_secteur=secteur_nom).first()
                if not secteur:
                    secteur = Secteur(nom_secteur=secteur_nom)
                    db.session.add(secteur)
                    db.session.flush() # Génère l'ID du secteur immédiatement sans valider la transaction complète
                
                # --- RÈGLE MÉTIER 3 : Gérer l'Entreprise ---
                # On cherche si l'entreprise existe déjà en base (par son nom unique), sinon on la crée
                entreprise_nom = raw_job["nom_entreprise"]
                entreprise = Entreprise.query.filter_by(nom_entreprise=entreprise_nom).first()
                if not entreprise:
                    # Crée l'entreprise et l'associe au secteur d'activité
                    entreprise = Entreprise(
                        nom_entreprise=entreprise_nom,
                        localisation=raw_job["localisation"],
                        id_secteur=secteur.id_secteur
                    )
                    db.session.add(entreprise)
                    db.session.flush() # Génère l'ID de l'entreprise
                
                # --- RÈGLE MÉTIER 4 : Création de l'Offre d'Emploi ---
                new_job = OffreEmploi(
                    linkedin_job_id=raw_job["linkedin_job_id"],
                    titre_poste=raw_job["titre_poste"],
                    description=raw_job["description"],
                    id_entreprise=entreprise.id_entreprise,
                    id_secteur=secteur.id_secteur,
                    date_scraping=datetime.now()
                )
                
                # --- RÈGLE MÉTIER 5 : Détection et association des compétences ---
                # On analyse la description brute de l'offre d'emploi
                description_lower = raw_job["description"].lower()
                
                for skill_name, keywords_list in self.skills_dictionary.items():
                    # On vérifie si l'un des mots-clés de la compétence est présent dans le texte
                    # ex: si "python" ou "py" est dans la description de l'offre
                    if any(kw in description_lower for keywords_list_item in keywords_list for kw in [keywords_list_item]):
                        # On cherche si la compétence existe déjà dans la table 'competence'
                        competence = Competence.query.filter_by(nom_competence=skill_name).first()
                        if not competence:
                            # Crée la compétence si elle n'existe pas encore
                            competence = Competence(
                                nom_competence=skill_name,
                                type_competence="Technique" if skill_name != "Anglais" and skill_name != "Communication" else "Humaine"
                            )
                            db.session.add(competence)
                            db.session.flush()
                        
                        # Association Many-to-Many : on ajoute la compétence à la liste de l'offre
                        # SQLAlchemy se charge d'insérer la ligne dans la table pivot 'offre_competence' automatiquement !
                        new_job.competences.append(competence)
                
                # Ajout de l'offre complète à la session
                db.session.add(new_job)
                new_jobs_count += 1
                logs.append(f"Offre enregistrée : {new_job.titre_poste} chez {entreprise_nom}")

            except Exception as job_error:
                logs.append(f"Erreur lors du traitement de l'offre {raw_job.get('titre_poste')} : {str(job_error)}")
                db.session.rollback() # Annule les modifications pour cette offre spécifique en cas d'erreur
                continue

        # 3. Validation de toutes les insertions réussies dans PostgreSQL
        try:
            db.session.commit()
            logs.append(f"Scraping terminé : {new_jobs_count} nouvelle(s) offre(s) enregistrée(s).")
        except Exception as commit_error:
            logs.append(f"Erreur lors de l'enregistrement final : {str(commit_error)}")
            db.session.rollback()
            new_jobs_count = 0

        return {"new_jobs": new_jobs_count, "total_found": len(raw_jobs), "logs": logs}

    def get_all_jobs(self):
        """Retourne toutes les offres d'emploi enregistrées en base."""
        return OffreEmploi.query.order_by(OffreEmploi.date_scraping.desc()).all()

    def get_recent_jobs(self, limit=5):
        """Retourne les dernières offres d'emploi collectées."""
        return OffreEmploi.query.order_by(OffreEmploi.date_scraping.desc()).limit(limit).all()

    def get_offres_filtered(self, keyword=None, secteur_id=None, location=None):
        """Retourne les offres d'emploi correspondant aux filtres de recherche fournis."""
        query = OffreEmploi.query
        if keyword:
            query = query.filter(OffreEmploi.titre_poste.ilike(f"%{keyword}%"))
        if secteur_id:
            query = query.filter(OffreEmploi.id_secteur == secteur_id)
        if location:
            query = query.join(Entreprise).filter(Entreprise.localisation.ilike(f"%{location}%"))
        return query.order_by(OffreEmploi.date_scraping.desc()).all()

    def get_dashboard_kpis(self):
        """Calcule les indicateurs clés affichés sur le tableau de bord."""
        derniere_offre = OffreEmploi.query.order_by(OffreEmploi.date_scraping.desc()).first()
        return {
            "offres_collectees": OffreEmploi.query.count(),
            "entreprises": Entreprise.query.count(),
            "secteurs_couverts": Secteur.query.count(),
            "competences_detectees": Competence.query.count(),
            "derniere_maj": derniere_offre.date_scraping.strftime("%d/%m/%Y %H:%M") if derniere_offre else "N/A"
        }


class AnalyticsService:
    """
    Service dédié aux analyses agrégées (secteurs, compétences, évolutions, rapports).
    Il applique le Principe de Responsabilité Unique : lecture/agrégation seulement,
    aucune écriture en base et aucune connaissance du scraping.
    """

    MOIS_FR = ["", "Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]
    # Couleur selon le rang : 1er = vert, 2e = orange, 3e = bleu (le reste retombe sur l'indigo de "Autres")
    DONUT_COLORS = ["#10B981", "#F59E0B", "#0A66C2"]
    DONUT_AUTRES_COLOR = "#6366F1"
    DONUT_RADIUS = 38

    def get_top_secteurs(self, limit=5):
        """Retourne les secteurs classés par nombre d'offres, avec une échelle relative au premier."""
        rows = db.session.query(Secteur.nom_secteur, func.count(OffreEmploi.id_offre).label("total")) \
            .join(OffreEmploi, OffreEmploi.id_secteur == Secteur.id_secteur) \
            .group_by(Secteur.id_secteur) \
            .order_by(func.count(OffreEmploi.id_offre).desc()) \
            .limit(limit).all()
        max_total = rows[0].total if rows else 0
        return [
            {"nom": r.nom_secteur, "total": r.total, "pourcentage": round(r.total / max_total * 100) if max_total else 0}
            for r in rows
        ]

    def get_top_competences(self, limit=10):
        """Retourne les compétences les plus fréquentes dans les offres collectées."""
        rows = db.session.query(Competence.nom_competence, func.count(OffreCompetence.id_offre).label("total")) \
            .join(OffreCompetence, OffreCompetence.id_competence == Competence.id_competence) \
            .group_by(Competence.id_competence) \
            .order_by(func.count(OffreCompetence.id_offre).desc()) \
            .limit(limit).all()
        max_total = rows[0].total if rows else 0
        return [
            {"nom": r.nom_competence, "total": r.total, "pourcentage": round(r.total / max_total * 100) if max_total else 0}
            for r in rows
        ]

    def get_competences_word_cloud(self, limit=16):
        """Retourne les compétences les plus fréquentes avec une taille de police proportionnelle à leur fréquence."""
        competences = self.get_top_competences(limit=limit)
        for c in competences:
            c["taille"] = 11 + round(c["pourcentage"] / 100 * 15)
            c["opacite"] = round(0.5 + c["pourcentage"] / 100 * 0.5, 2)
        return competences

    def get_top_competences_by_secteur(self, secteur_id=None, limit=5):
        """Retourne les noms des compétences les plus demandées, filtrées sur un secteur si précisé."""
        query = db.session.query(Competence.nom_competence, func.count(OffreCompetence.id_offre).label("total")) \
            .join(OffreCompetence, OffreCompetence.id_competence == Competence.id_competence) \
            .join(OffreEmploi, OffreEmploi.id_offre == OffreCompetence.id_offre)
        if secteur_id:
            query = query.filter(OffreEmploi.id_secteur == secteur_id)
        rows = query.group_by(Competence.id_competence) \
            .order_by(func.count(OffreCompetence.id_offre).desc()) \
            .limit(limit).all()
        return [r.nom_competence for r in rows]

    def get_competence_type_breakdown(self):
        """Retourne la répartition des mentions de compétences entre types (Technique / Humaine)."""
        rows = db.session.query(Competence.type_competence, func.count(OffreCompetence.id_offre).label("total")) \
            .join(OffreCompetence, OffreCompetence.id_competence == Competence.id_competence) \
            .group_by(Competence.type_competence).all()
        total = sum(r.total for r in rows) or 1
        return [
            {"type": r.type_competence or "Autre", "total": r.total, "pourcentage": round(r.total / total * 100)}
            for r in sorted(rows, key=lambda r: r.total, reverse=True)
        ]

    def get_monthly_volume(self, months=6):
        """Retourne le nombre d'offres collectées par mois sur la période demandée."""
        since = datetime.now() - timedelta(days=30 * months)
        rows = db.session.query(
            extract("year", OffreEmploi.date_scraping).label("annee"),
            extract("month", OffreEmploi.date_scraping).label("mois"),
            func.count(OffreEmploi.id_offre).label("total")
        ).filter(OffreEmploi.date_scraping >= since) \
         .group_by("annee", "mois") \
         .order_by("annee", "mois").all()
        max_total = max((r.total for r in rows), default=0)
        # Au-delà de 12 mois, on précise l'année dans le libellé pour éviter toute ambiguïté
        # entre deux occurrences du même mois sur des années différentes.
        include_year = months > 12
        return [
            {
                "label": f"{self.MOIS_FR[int(r.mois)]} {int(r.annee) % 100:02d}" if include_year else self.MOIS_FR[int(r.mois)],
                "total": r.total,
                "pourcentage": round(r.total / max_total * 100) if max_total else 0
            }
            for r in rows
        ]

    def get_geo_distribution(self, limit=5):
        """Retourne la répartition géographique des offres, basée sur la localisation des entreprises."""
        rows = db.session.query(Entreprise.localisation, func.count(OffreEmploi.id_offre).label("total")) \
            .join(OffreEmploi, OffreEmploi.id_entreprise == Entreprise.id_entreprise) \
            .filter(Entreprise.localisation.isnot(None), Entreprise.localisation != "") \
            .group_by(Entreprise.localisation) \
            .order_by(func.count(OffreEmploi.id_offre).desc()) \
            .limit(limit).all()
        return [{"lieu": r.localisation, "total": r.total} for r in rows]

    def get_secteur_repartition_donut(self, top_n=3):
        """Calcule les segments (tracé SVG) d'un graphique en anneau représentant la part de chaque secteur."""
        total_offres = OffreEmploi.query.count()
        secteurs_couverts = Secteur.query.count()
        if total_offres == 0:
            return {"segments": [], "secteurs_couverts": secteurs_couverts}

        top = self.get_top_secteurs(limit=top_n)
        circonference = round(2 * pi * self.DONUT_RADIUS, 2)
        cumul = 0
        segments = []
        for i, s in enumerate(top):
            part = round(s["total"] / total_offres * 100)
            dash = round(s["total"] / total_offres * circonference, 2)
            segments.append({
                "nom": s["nom"], "pourcentage": part, "dash": dash,
                "reste": round(circonference - dash, 2), "offset": round(-cumul, 2),
                "couleur": self.DONUT_COLORS[i] if i < len(self.DONUT_COLORS) else self.DONUT_AUTRES_COLOR
            })
            cumul += dash

        autres_total = total_offres - sum(s["total"] for s in top)
        if autres_total > 0:
            part = round(autres_total / total_offres * 100)
            dash = round(circonference - cumul, 2)
            segments.append({
                "nom": "Autres", "pourcentage": part, "dash": dash,
                "reste": round(circonference - dash, 2), "offset": round(-cumul, 2),
                "couleur": self.DONUT_AUTRES_COLOR
            })

        return {"segments": segments, "secteurs_couverts": secteurs_couverts}

    def get_growth_secteurs(self, limit=4):
        """
        Compare, pour chaque secteur, le nombre d'offres collectées sur les 30 derniers jours
        à celui des 30 jours précédents, pour identifier les secteurs en forte croissance.
        """
        now = datetime.now()
        debut_recent = now - timedelta(days=30)
        debut_precedent = now - timedelta(days=60)

        resultats = []
        for secteur in Secteur.query.all():
            recent = OffreEmploi.query.filter(
                OffreEmploi.id_secteur == secteur.id_secteur,
                OffreEmploi.date_scraping >= debut_recent
            ).count()
            precedent = OffreEmploi.query.filter(
                OffreEmploi.id_secteur == secteur.id_secteur,
                OffreEmploi.date_scraping >= debut_precedent,
                OffreEmploi.date_scraping < debut_recent
            ).count()

            if recent == 0 and precedent == 0:
                continue
            croissance = round((recent - precedent) / precedent * 100) if precedent > 0 else 100
            resultats.append({"nom": secteur.nom_secteur, "croissance": croissance, "recent": recent})

        resultats.sort(key=lambda r: r["croissance"], reverse=True)
        return resultats[:limit]

    def create_rapport(self, user_id, titre_rapport, secteur_id=None):
        """Génère et enregistre un rapport personnalisé listant les compétences les plus demandées d'un secteur."""
        top_skills = self.get_top_competences_by_secteur(secteur_id, limit=5)
        rapport = RapportPersonnalise(
            titre_rapport=titre_rapport,
            competences_recherchees=", ".join(top_skills) if top_skills else "Aucune donnée disponible pour ce secteur.",
            id_user=user_id,
            id_secteur=secteur_id
        )
        db.session.add(rapport)
        db.session.commit()
        return rapport

    def get_rapports_for_user(self, user_id):
        """Retourne les rapports personnalisés déjà générés par un utilisateur, du plus récent au plus ancien."""
        return RapportPersonnalise.query.filter_by(id_user=user_id) \
            .order_by(RapportPersonnalise.date_creation.desc()).all()
