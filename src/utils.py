import re
import requests
from typing import Tuple, List, Optional
from .config import Config
import urllib.parse
import os
from pathlib import Path

def extract_id_and_code(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Extrait l'ID et le code CRM d'une URL iframe."""
    if not url:
        return None, None
    id_match = re.search(r'ID=([^&]+)', url)
    code_match = re.search(r'CODE=([^&]+)', url)
    return (id_match.group(1) if id_match else None,
            code_match.group(1) if code_match else None)

def create_session():
    """Crée une session avec des paramètres optimisés et sécurisés."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': Config.USER_AGENT,
        # Ajouter des en-têtes de sécurité supplémentaires
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'DNT': '1',  # Do Not Track
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1'
    })
    return session

def is_valid_url(url: str) -> bool:
    """
    Valide qu'une URL est bien formée et utilise un schéma sécurisé.
    
    Args:
        url: L'URL à valider
    
    Returns:
        bool: True si l'URL est valide, False sinon
    """
    if not url or not isinstance(url, str):
        return False
    
    # Vérifier la structure générale de l'URL
    url_pattern = re.compile(
        r'^(https?://)'  # http:// ou https:// obligatoire
        r'([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?'  # domaine
        r'(/[a-zA-Z0-9._~:/?#[\]@!$&\'()*+,;=%-]*)?$'  # chemin, paramètres, etc.
    )
    
    if not url_pattern.match(url):
        return False
    
    # Assurer qu'il n'y a pas d'espaces ou caractères d'échappement
    if ' ' in url or '\\' in url:
        return False
    
    # Vérifier que le schéma est bien http ou https
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False
    
    # S'assurer qu'il y a bien un hostname
    if not parsed.netloc:
        return False
    
    # Vérifier que l'URL n'est pas une adresse IP locale ou privée
    hostname = parsed.netloc.split(':')[0]  # Extraire le hostname sans le port
    
    # Bloquer les adresses IP locales courantes et les boucles locales
    if (hostname == 'localhost' or 
        hostname.startswith('127.') or 
        hostname.startswith('192.168.') or 
        hostname.startswith('10.') or 
        hostname.startswith('172.16.') or
        hostname.startswith('169.254.') or
        hostname == '0.0.0.0'):
        return False
    
    return True

def sanitize_urls(urls: List[str]) -> List[str]:
    """
    Filtre une liste d'URLs pour ne garder que celles qui sont valides.
    
    Args:
        urls: Liste d'URLs à valider
        
    Returns:
        List[str]: Liste d'URLs valides
    """
    if not urls:
        return []
    
    return [url for url in urls if is_valid_url(url)]

def sanitize_html(html_content: str) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    
    Args:
        html_content: The HTML content to sanitize
        
    Returns:
        str: Sanitized HTML content
    """
    # Remplacer les caractères potentiellement dangereux
    html_content = html_content.replace('<', '&lt;').replace('>', '&gt;')
    html_content = html_content.replace('"', '&quot;').replace("'", '&#39;')
    
    return html_content

def get_project_root() -> Path:
    """Retourne le répertoire racine du projet de façon cross-platform."""
    return Path(__file__).parent.parent

def get_data_file_path(filename: str) -> Path:
    """Retourne le chemin vers un fichier dans le dossier data."""
    return get_project_root() / "data" / filename