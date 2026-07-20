# app/scraping/lefaso_client.py
#
# Client de collecte pour le site public "Emploi LeFaso.net"
# (https://emploi.lefaso.net), source complémentaire au scraping LinkedIn et à
# l'API France Travail, pour diversifier la couverture des offres publiées au
# Burkina Faso (voir RAPPORT_PROJET.md, section 5.7).
#
# Contrairement à LinkedIn (page dynamique nécessitant Playwright), ce site est
# une page SPIP classique rendue côté serveur : son contenu est présent tel
# quel dans le HTML brut, sans exécution JavaScript. Une simple requête HTTP
# (requests + BeautifulSoup) suffit donc, plus léger et moins fragile qu'un
# navigateur piloté.
#
# Le robots.txt du site (consulté le 19/07/2026) autorise l'exploration des
# pages de recherche et de détail d'offre, avec un délai minimal de 1s entre
# requêtes (Crawl-delay: 1), respecté ci-dessous entre chaque page de détail.

import time
import random
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://emploi.lefaso.net/"
SEARCH_URL = BASE_URL + "spip.php"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class LefasoEmploiClient:
    """
    Recherche et extraction d'offres d'emploi publiques sur emploi.lefaso.net,
    site burkinabè d'annonces d'emploi (CMS SPIP, contenu statique côté serveur).
    """

    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"})

    def search_offres(self, mots_cles, limit=10):
        """
        Recherche des offres par mots-clés et retourne des dictionnaires normalisés,
        directement exploitables par ScrapingService.run_lefaso_and_persist.
        """
        response = self.session.get(
            SEARCH_URL, params={"page": "recherche_offre", "recherche": mots_cles}, timeout=20
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        offres = []
        for titre_h2 in soup.select("h2.offre-title")[:limit]:
            lien = titre_h2.select_one("a[href]")
            if not lien or not lien.get("href"):
                continue
            url_detail = urljoin(BASE_URL, lien["href"])
            titre_poste = lien.get_text(strip=True)

            subtitle = titre_h2.find_next_sibling("span", class_="offre-subtitle")
            nom_entreprise, localisation = self._parse_subtitle(subtitle)

            # Respecte le Crawl-delay: 1 annoncé par le robots.txt du site entre deux requêtes.
            time.sleep(1 + random.uniform(0, 0.5))
            description = self._fetch_description(url_detail)

            slug = url_detail.rsplit("/", 1)[-1]
            if slug.endswith(".html"):
                slug = slug[:-5]

            offres.append({
                "id_externe": f"LEFASO-{slug}",
                "titre_poste": titre_poste or "Intitulé non précisé",
                "description": description,
                "nom_entreprise": nom_entreprise,
                "localisation": localisation,
            })

        return offres

    @staticmethod
    def _parse_subtitle(subtitle):
        """
        Extrait l'entreprise (optionnelle) et la localisation depuis le bloc
        `.offre-subtitle`, dont la structure varie légèrement selon que le site
        a renseigné ou non le nom du recruteur pour cette offre.
        """
        if not subtitle:
            return "Entreprise non précisée", ""
        spans = subtitle.find_all("span")
        localisation = spans[-1].get_text(strip=True) if spans else ""
        lien_entreprise = subtitle.find("a")
        texte_entreprise = lien_entreprise.get_text(strip=True) if lien_entreprise else ""
        nom_entreprise = texte_entreprise if texte_entreprise else "Entreprise non précisée"
        return nom_entreprise, localisation

    def _fetch_description(self, url_detail):
        """Récupère la description complète (non tronquée) depuis la page de détail de l'offre."""
        try:
            response = self.session.get(url_detail, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            bloc = soup.select_one("div.texte")
            return bloc.get_text(separator="\n", strip=True) if bloc else "Description non disponible."
        except requests.RequestException:
            return "Description non disponible."
