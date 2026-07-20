# app/scraping/france_travail_client.py
#
# Client pour l'API publique "Offres d'emploi v2" de France Travail (ex Pôle
# Emploi), en complément du scraping LinkedIn : source officielle, sans risque
# de blocage anti-robot, avec des données déjà structurées par la source
# elle-même (secteur ROME, compétences du référentiel officiel) plutôt que
# devinées à partir d'un mot-clé de recherche ou d'une correspondance de
# sous-chaînes.
#
# Nécessite un compte développeur gratuit sur https://francetravail.io :
# créer une application, s'abonner à l'API "Offres d'emploi v2", puis
# renseigner FRANCE_TRAVAIL_CLIENT_ID / FRANCE_TRAVAIL_CLIENT_SECRET dans .env
#
# Portée géographique : cette API ne couvre que les offres publiées en France.
# Elle vient donc diversifier le point de comparaison hors Burkina Faso déjà
# présent dans la rotation (scheduler.py), pas remplacer la couverture Burkina
# Faso, qui reste assurée par le scraping LinkedIn.

import time
import requests

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
DEFAULT_SCOPE = "api_offresdemploiv2 o2dsoffre"


class FranceTravailClient:
    """
    Authentification OAuth2 (client credentials grant) et recherche d'offres
    d'emploi via l'API officielle France Travail.
    """

    def __init__(self, client_id, client_secret, scope=DEFAULT_SCOPE):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self._access_token = None
        self._expires_at = 0

    def _get_token(self):
        """Récupère un jeton d'accès, en le réutilisant tant qu'il n'est pas expiré."""
        if self._access_token and time.time() < self._expires_at:
            return self._access_token

        response = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": self.scope,
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        self._access_token = payload["access_token"]
        # Marge de sécurité de 60s pour ne jamais utiliser un jeton expiré pile
        # au moment de la requête suivante.
        self._expires_at = time.time() + payload.get("expires_in", 1200) - 60
        return self._access_token

    def search_offres(self, mots_cles, commune=None, distance=None, range_str="0-49"):
        """
        Recherche des offres d'emploi par mots-clés (et optionnellement par
        commune, code INSEE).

        Returns:
            list[dict]: offres normalisées, directement exploitables par
            ScrapingService.run_france_travail_and_persist.
        """
        params = {"motsCles": mots_cles, "range": range_str}
        if commune:
            params["commune"] = commune
        if distance is not None:
            params["distance"] = distance

        headers = {"Authorization": f"Bearer {self._get_token()}"}
        response = requests.get(SEARCH_URL, headers=headers, params=params, timeout=20)

        # 204 = aucune offre ne correspond aux critères : comportement normal
        # de cette API pour une recherche vide, pas une erreur à signaler.
        if response.status_code == 204:
            return []
        response.raise_for_status()

        offres_brutes = response.json().get("resultats", [])
        return [self._normaliser(offre) for offre in offres_brutes]

    @staticmethod
    def _normaliser(offre):
        """
        Convertit une offre brute de l'API en dictionnaire simple, dans un
        format déjà proche de celui produit par LinkedInScraper.scrape_jobs,
        mais enrichi des champs structurés propres à cette source (secteur,
        type de contrat, compétences) que le scraping LinkedIn doit deviner.
        """
        entreprise = offre.get("entreprise") or {}
        lieu = offre.get("lieuTravail") or {}
        competences = [c["libelle"] for c in offre.get("competences", []) if c.get("libelle")]

        return {
            "id_externe": f"FT-{offre['id']}",
            "titre_poste": offre.get("intitule") or "Intitulé non précisé",
            "description": offre.get("description") or "Description non disponible.",
            "nom_entreprise": entreprise.get("nom") or "Entreprise non précisée",
            "localisation": lieu.get("libelle") or "",
            # romeLibelle (métier ROME) est plus précis que secteurActiviteLibelle
            # (secteur NAF, souvent trop générique) ; les deux viennent de la
            # source elle-même, pas d'une déduction locale.
            "secteur": offre.get("romeLibelle") or offre.get("secteurActiviteLibelle") or "Non catégorisé",
            "type_contrat": offre.get("typeContratLibelle") or offre.get("typeContrat") or "",
            "competences": competences,
        }
