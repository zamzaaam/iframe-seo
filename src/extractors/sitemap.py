import requests
import xml.etree.ElementTree as ET
from typing import List
import logging
from ..config import Config
from ..utils import create_session, is_valid_url, sanitize_urls

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sitemap_extractor')

class SitemapExtractor:
    def __init__(self):
        self.session = create_session()
    
    def extract_urls(self, sitemap_url: str) -> List[str]:
        """Extrait les URLs d'un sitemap de façon sécurisée."""
        # Validation de l'URL du sitemap
        if not is_valid_url(sitemap_url):
            logger.warning(f"Invalid sitemap URL: {sitemap_url}")
            return []

        try:
            # Limiter le temps et la taille de réponse
            response = self.session.get(sitemap_url, timeout=Config.TIMEOUT)
            
            if response.status_code != 200:
                logger.info(f"Non-200 status code ({response.status_code}) for sitemap: {sitemap_url}")
                return []

            # Vérification du type de contenu
            content_type = response.headers.get('Content-Type', '')
            valid_types = ['text/xml', 'application/xml', 'application/rss+xml', 'application/atom+xml']
            if not any(valid_type in content_type for valid_type in valid_types):
                # Vérifier quand même si le contenu ressemble à du XML
                if not response.text.strip().startswith('<?xml'):
                    logger.warning(f"Invalid content type for sitemap: {content_type}")
                    return []

            # Limite la taille du contenu 
            max_content_size = 10 * 1024 * 1024  # 10 MB
            if len(response.content) > max_content_size:
                logger.warning(f"Sitemap content too large: {sitemap_url}")
                return []

            try:
                # Utilisation d'un traitement XML sécurisé
                root = ET.fromstring(response.content)
                
                # Détection du namespace
                ns = None
                if root.tag.startswith('{'):
                    ns_end = root.tag.find('}')
                    if ns_end >= 0:
                        ns = {'ns': root.tag[1:ns_end]}
                
                urls = []
                if ns:
                    # Avec namespace
                    for loc in root.findall('.//ns:loc', ns):
                        if loc.text and is_valid_url(loc.text):
                            urls.append(loc.text)
                else:
                    # Sans namespace
                    for loc in root.findall('.//loc'):
                        if loc.text and is_valid_url(loc.text):
                            urls.append(loc.text)
                
                logger.info(f"Extracted {len(urls)} URLs from sitemap: {sitemap_url}")
                return urls

            except ET.ParseError as e:
                logger.error(f"XML parsing error in sitemap {sitemap_url}: {str(e)}")
                return []

        except Exception as e:
            logger.error(f"Error processing sitemap {sitemap_url}: {str(e)}")
            return []