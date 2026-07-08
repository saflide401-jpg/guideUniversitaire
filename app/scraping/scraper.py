# app/scraping/scraper.py
import random  # Génère des délais aléatoires entre les actions
from urllib.parse import urlencode  # Encode correctement les paramètres de recherche dans l'URL
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class LinkedInScraper:
    """
    Classe responsable du pilotage de Playwright pour extraire les offres d'emploi LinkedIn
    via l'interface publique (sans connexion), afin d'éviter tout risque de bannissement de compte.

    Playwright a remplacé Selenium ici : son moteur d'attente automatique (auto-waiting) sur
    la visibilité et l'actionnabilité des éléments évite la classe de bugs rencontrée avec Selenium,
    où WebElement.text renvoyait une chaîne vide pour des cartes sorties du viewport après un scroll.
    """

    def __init__(self):
        self.viewport = {"width": 1920, "height": 1080}

    def _is_blocked(self, url):
        """
        Détecte si LinkedIn a redirigé vers un mur de connexion (/authwall)
        ou un point de contrôle anti-bot (/checkpoint), fréquent en accès public/anonyme
        après un certain volume de requêtes depuis la même IP.
        Retourne True si un blocage est détecté, False sinon.
        """
        current_url = url.lower()
        blocked_markers = ["authwall", "checkpoint", "login"]
        return any(marker in current_url for marker in blocked_markers)

    def scrape_jobs(self, keywords, location, limit=5):
        """
        Scrape les offres d'emploi publiques sur LinkedIn selon des critères.

        Args:
            keywords (str) : Les mots-clés de recherche (ex: "Développeur Python")
            location (str) : La localisation (ex: "Paris")
            limit (int) : Le nombre maximum d'offres à récupérer (par défaut 5).
                          Note : la recherche publique sans connexion est limitée par
                          LinkedIn à un nombre restreint de résultats (~25 selon la
                          localisation). Une valeur trop élevée ne renverra pas plus
                          de résultats que ce plafond.

        Returns:
            list: Une liste de dictionnaires contenant les données brutes des offres
        """
        jobs_data = []

        # urlencode() encode correctement chaque paramètre (ex: "Île-de-France" -> "%C3%8Ele-de-France")
        params = {"keywords": keywords, "location": location}
        search_url = f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"

        with sync_playwright() as p:
            browser = None
            try:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=USER_AGENT, locale="fr-FR", viewport=self.viewport
                )
                page = context.new_page()

                print(f"[SCRAPER] Navigation vers l'URL : {search_url}")
                page.goto(search_url, wait_until="domcontentloaded")

                # Vérification immédiate après le chargement : LinkedIn a-t-il redirigé
                # vers un mur de connexion ou un CAPTCHA au lieu de la page de résultats ?
                if self._is_blocked(page.url):
                    print(
                        "[SCRAPER] Accès bloqué par LinkedIn (authwall/checkpoint détecté). "
                        "Ceci indique généralement un rate-limiting sur l'IP du conteneur. "
                        "Réessayez plus tard ou depuis une autre IP."
                    )
                    return jobs_data  # retourne une liste vide plutôt qu'une erreur générique masquée

                page.wait_for_selector(".jobs-search__results-list", timeout=5000)

                for _ in range(2):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    page.wait_for_timeout(random.uniform(1200, 2500))

                job_cards = page.query_selector_all(".jobs-search__results-list > li")
                print(f"[SCRAPER] {len(job_cards)} cartes d'offres détectées sur la page.")

                for i, card in enumerate(job_cards[:limit]):
                    detail_page = None
                    try:
                        print(f"[SCRAPER] Extraction de l'offre {i+1}/{limit}...")

                        # Le double scroll précédent laisse les premières cartes hors du viewport
                        # visible : on les ramène en vue avant de lire leurs champs.
                        card.scroll_into_view_if_needed()

                        # LinkedIn place data-entity-urn sur le <div class="base-card"> imbriqué,
                        # pas sur le <li> de la carte lui-même : on doit descendre d'un niveau.
                        base_card = card.query_selector(".base-card")
                        if not base_card:
                            print(f"[WARN] Offre {i+1} ignorée : bloc .base-card introuvable sur la carte.")
                            continue
                        raw_urn = base_card.get_attribute("data-entity-urn")
                        if not raw_urn:
                            print(f"[WARN] Offre {i+1} ignorée : attribut data-entity-urn introuvable sur la carte.")
                            continue
                        linkedin_job_id = raw_urn.split(":")[-1]

                        titre_poste = card.query_selector(".base-search-card__title").inner_text().strip()
                        nom_entreprise = card.query_selector(".base-search-card__subtitle").inner_text().strip()
                        localisation = card.query_selector(".job-search-card__location").inner_text().strip()

                        job_url = card.query_selector(".base-card__full-link").get_attribute("href")

                        # Playwright ouvre simplement une nouvelle page dans le même contexte,
                        # sans jonglage de handles de fenêtre comme avec Selenium.
                        detail_page = context.new_page()
                        detail_page.goto(job_url, wait_until="domcontentloaded")

                        # LinkedIn peut aussi bloquer sur la page de détail même si la liste a chargé
                        if self._is_blocked(detail_page.url):
                            print(f"[SCRAPER] Blocage détecté sur la page de détail de l'offre {linkedin_job_id}.")
                            detail_page.close()
                            continue

                        detail_page.wait_for_timeout(random.uniform(800, 1500))
                        description = ""

                        # Clic sur "Voir plus" pour récupérer la description complète : LinkedIn la tronque
                        # par défaut, ce qui ferait rater des mots-clés à la détection de compétences.
                        try:
                            detail_page.click("button.show-more-less-html__button", timeout=2000)
                            detail_page.wait_for_timeout(500)
                        except PlaywrightTimeoutError:
                            pass  # bouton absent = description déjà entièrement affichée

                        try:
                            desc_element = detail_page.wait_for_selector(
                                ".show-more-less-html__markup", timeout=3000
                            )
                            description = desc_element.inner_text().strip()
                        except PlaywrightTimeoutError:
                            print(f"[WARN] Impossible de charger la description pour l'offre {linkedin_job_id}")
                            description = "Description non disponible."

                        detail_page.close()
                        detail_page = None

                        jobs_data.append({
                            "linkedin_job_id": linkedin_job_id,
                            "titre_poste": titre_poste,
                            "nom_entreprise": nom_entreprise,
                            "localisation": localisation,
                            "description": description
                        })

                        page.wait_for_timeout(random.uniform(800, 2000))

                    except Exception as card_error:
                        print(f"[ERROR] Erreur lors de l'extraction d'une carte d'offre : {str(card_error)}")
                        if detail_page:
                            detail_page.close()
                        continue

            except Exception as global_error:
                print(f"[ERROR] Erreur globale lors du scraping : {str(global_error)}")

            finally:
                if browser:
                    print("[SCRAPER] Fermeture du navigateur...")
                    browser.close()

        return jobs_data
