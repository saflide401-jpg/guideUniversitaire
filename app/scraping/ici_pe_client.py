# app/scraping/ici_pe_client.py
#
# Client de collecte pour le site public ICI Partenaires Entreprises
# (ici-pe.com/jobs), cabinet de recrutement burkinabè, source complémentaire à
# LinkedIn, France Travail et Emploi LeFaso.net (voir RAPPORT_PROJET.md,
# section 5.8).
#
# Le site utilise le plugin WordPress "WP Job Manager" : la liste des offres
# est chargée par le navigateur via un point d'entrée AJAX dédié
# (/jm-ajax/get_listings/) qui renvoie du JSON contenant un fragment HTML des
# offres — la page brute ne contient donc aucune offre, mais ce point d'entrée
# JSON est directement appelable sans navigateur, plus léger qu'une automatisation
# Playwright.
#
# Le robots.txt du site (consulté le 19/07/2026) n'interdit que /wp-admin/ et
# des chemins liés au panier e-commerce (WooCommerce, sans rapport avec les
# offres) : les chemins /jm-ajax/ et /poste/ utilisés ici ne sont pas concernés.

import time
import random
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.ici-pe.com"
AJAX_URL = BASE_URL + "/jm-ajax/get_listings/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class IciPeClient:
    """
    Recherche et extraction d'offres d'emploi publiques sur ici-pe.com/jobs
    (cabinet de recrutement burkinabè, plugin WordPress "WP Job Manager").
    """

    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"})

    def search_offres(self, mots_cles, limit=10):
        """
        Recherche des offres par mots-clés et retourne des dictionnaires normalisés,
        directement exploitables par ScrapingService.run_ici_pe_and_persist.
        """
        response = self.session.get(
            AJAX_URL,
            params={"search_keywords": mots_cles, "search_location": "", "page": 1, "per_page": limit},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("found_jobs"):
            return []

        soup = BeautifulSoup(payload.get("html", ""), "html.parser")

        offres = []
        for item in soup.select("li.job_listing")[:limit]:
            lien = item.select_one("a[href]")
            if not lien or not lien.get("href"):
                continue
            url_detail = lien["href"]

            titre_el = item.select_one("h3")
            titre_poste = titre_el.get_text(strip=True) if titre_el else "Intitulé non précisé"

            company_el = item.select_one("div.company strong") or item.select_one("div.company")
            nom_entreprise = company_el.get_text(strip=True) if company_el else "Entreprise non précisée"

            location_el = item.select_one("div.location")
            localisation = location_el.get_text(strip=True) if location_el else ""

            # ID unique : "post-{id}" est déjà présent comme classe CSS sur le <li>.
            classes = item.get("class", [])
            post_id = next((c.replace("post-", "") for c in classes if c.startswith("post-")), None)
            if not post_id:
                continue

            # Politesse : le robots.txt du site n'impose pas de Crawl-delay explicite,
            # mais on espace quand même les requêtes de détail par prudence, comme pour
            # les autres sources (voir lefaso_client.py).
            time.sleep(1 + random.uniform(0, 0.5))
            description = self._fetch_description(url_detail)

            offres.append({
                "id_externe": f"ICIPE-{post_id}",
                "titre_poste": titre_poste,
                "description": description,
                "nom_entreprise": nom_entreprise,
                "localisation": localisation,
            })

        return offres

    def _fetch_description(self, url_detail):
        """Récupère la description complète depuis la page de détail de l'offre."""
        try:
            response = self.session.get(url_detail, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            bloc = soup.select_one("div.job_description")
            return bloc.get_text(separator="\n", strip=True) if bloc else "Description non disponible."
        except requests.RequestException:
            return "Description non disponible."
