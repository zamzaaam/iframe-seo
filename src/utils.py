import re
import requests
from typing import Tuple
from .config import Config

def extract_id_and_code(url: str) -> Tuple[str, str]:
    """Extrait l'ID et le code CRM d'une URL iframe."""
    if not url:
        return None, None
    id_match = re.search(r'ID=([^&]+)', url)
    code_match = re.search(r'CODE=([^&]+)', url)
    return (id_match.group(1) if id_match else None,
            code_match.group(1) if code_match else None)

def create_session():
    """Crée une session avec des paramètres optimisés."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': Config.USER_AGENT
    })
    return session
