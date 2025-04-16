from typing import List, Dict
from bs4 import BeautifulSoup
from ..config import Config
from ..utils import create_session, extract_id_and_code

class IframeExtractor:
    def __init__(self):
        self.session = create_session()

    def extract_from_url(self, url: str) -> List[Dict]:
        """Extrait les liens iframe d'une URL donnée."""
        try:
            response = self.session.get(url, timeout=Config.TIMEOUT)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            try:
                main_section = soup.find("body").find("div").find("div").find("main")
                if not main_section:
                    return []

                results = []
                for iframe in main_section.find_all("iframe"):
                    src = iframe.get("src", "")
                    if src.startswith("https://ovh.slgnt.eu/optiext/"):
                        form_id, crm_code = extract_id_and_code(src)
                        results.append({
                            "URL source": url,
                            "Iframe": src,
                            "Form ID": form_id,
                            "CRM Campaign": crm_code
                        })
                return results

            except AttributeError:
                return []

        except Exception:
            return []
