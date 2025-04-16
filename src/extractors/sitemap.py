import requests
import xml.etree.ElementTree as ET
from typing import List
from ..config import Config
from ..utils import create_session

class SitemapExtractor:
    def __init__(self):
        self.session = create_session()
    
    def extract_urls(self, sitemap_url: str) -> List[str]:
        """Extrait les URLs d'un sitemap."""
        try:
            response = self.session.get(sitemap_url, timeout=Config.TIMEOUT)
            if response.status_code != 200:
                return []

            root = ET.fromstring(response.content)
            ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            urls = [loc.text for loc in root.findall('.//ns:loc', ns)]
            return urls

        except Exception:
            return []
