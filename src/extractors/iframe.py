from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import logging
from ..config import Config
from ..utils import create_session, extract_id_and_code, is_valid_url

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('iframe_extractor')

class IframeExtractor:
    def __init__(self):
        self.session = create_session()

    def extract_from_url(self, url: str) -> List[Dict]:
        """Extrait les liens iframe d'une URL donnée de façon sécurisée, en respectant le chemin spécifique."""
        # Validation de l'URL
        if not is_valid_url(url):
            logger.warning(f"Invalid URL format: {url}")
            return []

        try:
            # Limiter le temps de réponse pour éviter les attaques DoS
            response = self.session.get(url, timeout=Config.TIMEOUT)
            
            # Vérifier le code de statut HTTP
            if response.status_code != 200:
                logger.info(f"Non-200 status code ({response.status_code}) for URL: {url}")
                return []

            # Vérifier le type de contenu
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
                logger.info(f"Non-HTML content type ({content_type}) for URL: {url}")
                return []

            # Limite la taille du contenu pour éviter les attaques par épuisement de mémoire
            max_content_size = 10 * 1024 * 1024  # 10 MB
            if int(response.headers.get('Content-Length', 0)) > max_content_size:
                logger.warning(f"Content too large for URL: {url}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            
            # Uniquement suivre le chemin spécifique, comme dans le code d'origine
            results = []
            
            try:
                # Chercher exactement le chemin demandé: body > div > div > main
                main_section = soup.find("body").find("div").find("div").find("main")
                if not main_section:
                    logger.info(f"Specific path not found in {url}")
                    return []

                for iframe in main_section.find_all("iframe"):
                    src = iframe.get("src", "")
                    if src and src.startswith("https://ovh.slgnt.eu/optiext/"):
                        form_id, crm_code = extract_id_and_code(src)
                        # Vérifier que l'ID et le code sont valides
                        if form_id:
                            results.append({
                                "URL source": url,
                                "Iframe": src,
                                "Form ID": form_id,
                                "CRM Campaign": crm_code
                            })
            except (AttributeError, Exception) as e:
                logger.debug(f"Could not find specific path in {url}: {str(e)}")
                return []  # Si le chemin n'est pas trouvé, retourner une liste vide

            return results

        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            return []