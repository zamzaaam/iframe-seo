from typing import List, Dict, Any, Optional, Set, Tuple
import re
from urllib.parse import urlparse, urljoin
import xml.etree.ElementTree as ET
from ..config import Config
from ..utils import create_session

class SitemapDiscoveryExtractor:
    def __init__(self):
        self.session = create_session()
        self.discovered_sitemaps = []
        self.processed_urls = set()
    
    def extract_base_url(self, url: str) -> str:
        """Extrait l'URL de base à partir d'une URL complète."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    def discover_from_robots(self, base_url: str) -> List[str]:
        """Découvre les sitemaps à partir du fichier robots.txt."""
        robots_url = urljoin(base_url, "/robots.txt")
        sitemap_urls = []
        
        try:
            response = self.session.get(robots_url, timeout=Config.TIMEOUT)
            if response.status_code == 200:
                # Recherche des lignes "Sitemap: URL"
                for line in response.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        sitemap_url = line[8:].strip()
                        if sitemap_url and sitemap_url not in sitemap_urls:
                            sitemap_urls.append(sitemap_url)
        except Exception:
            pass
            
        return sitemap_urls
    
    def discover_standard_sitemaps(self, base_url: str) -> List[str]:
        """Tente de découvrir les emplacements standard de sitemaps."""
        standard_paths = [
            "/sitemap.xml",
            "/sitemap_index.xml",
            "/sitemapindex.xml",
            "/sitemap.php",
            "/sitemap.txt"
        ]
        
        found_sitemaps = []
        for path in standard_paths:
            sitemap_url = urljoin(base_url, path)
            try:
                response = self.session.head(sitemap_url, timeout=Config.TIMEOUT)
                if response.status_code == 200:
                    found_sitemaps.append(sitemap_url)
            except Exception:
                pass
                
        return found_sitemaps
    
    def check_if_sitemap_index(self, sitemap_url: str) -> Tuple[bool, List[str]]:
        """
        Vérifie si un sitemap est un index et extrait les URLs des sitemaps enfants.
        Retourne (is_index, child_sitemaps)
        """
        child_sitemaps = []
        is_index = False
        
        try:
            response = self.session.get(sitemap_url, timeout=Config.TIMEOUT)
            if response.status_code != 200:
                return False, []
            
            # Vérifier si c'est un sitemap index (contient des <sitemap> tags)
            root = ET.fromstring(response.content)
            
            # Détecter le namespace
            ns = None
            if root.tag.startswith('{'):
                ns_end = root.tag.find('}')
                if ns_end >= 0:
                    ns = {'ns': root.tag[1:ns_end]}
            
            # Chercher les balises <sitemap>
            if ns:
                sitemaps = root.findall('.//ns:sitemap', ns)
                if sitemaps:
                    is_index = True
                    for sitemap in sitemaps:
                        loc = sitemap.find('.//ns:loc', ns)
                        if loc is not None and loc.text:
                            child_sitemaps.append(loc.text)
            else:
                # Sans namespace
                sitemaps = root.findall('.//sitemap')
                if sitemaps:
                    is_index = True
                    for sitemap in sitemaps:
                        loc = sitemap.find('.//loc')
                        if loc is not None and loc.text:
                            child_sitemaps.append(loc.text)
                            
        except Exception:
            pass
            
        return is_index, child_sitemaps
    
    def discover_sitemaps(self, url: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """
        Découvre tous les sitemaps à partir d'une URL donnée.
        Retourne une liste de dictionnaires avec les propriétés de chaque sitemap.
        """
        self.discovered_sitemaps = []
        self.processed_urls = set()
        
        # Extraire l'URL de base
        base_url = self.extract_base_url(url)
        
        # Initialiser avec les sitemaps de robots.txt et les standards
        initial_sitemaps = self.discover_from_robots(base_url)
        initial_sitemaps.extend(self.discover_standard_sitemaps(base_url))
        
        # Éliminer les doublons
        initial_sitemaps = list(set(initial_sitemaps))
        
        # Traiter chaque sitemap découvert
        for sitemap_url in initial_sitemaps:
            self._process_sitemap(sitemap_url, 0, max_depth)
            
        return self.discovered_sitemaps
    
    def _process_sitemap(self, sitemap_url: str, depth: int, max_depth: int) -> None:
        """
        Traite un sitemap découvert et l'ajoute à la liste.
        Récursivement traite les sitemaps enfants si c'est un index.
        """
        if sitemap_url in self.processed_urls or depth > max_depth:
            return
            
        self.processed_urls.add(sitemap_url)
        
        # Vérifier si c'est un index
        is_index, child_sitemaps = self.check_if_sitemap_index(sitemap_url)
        
        # Ajouter ce sitemap à la liste
        sitemap_entry = {
            "url": sitemap_url,
            "is_index": is_index,
            "depth": depth,
            "children": child_sitemaps if is_index else [],
            "parent": None  # Sera mis à jour pour les enfants
        }
        
        self.discovered_sitemaps.append(sitemap_entry)
        
        # Si c'est un index, traiter récursivement les enfants
        if is_index and depth < max_depth:
            index_position = len(self.discovered_sitemaps) - 1
            
            for child_url in child_sitemaps:
                if child_url not in self.processed_urls:
                    self._process_sitemap(child_url, depth + 1, max_depth)
                    
                    # Marquer le parent pour ce sitemap enfant
                    for i, entry in enumerate(self.discovered_sitemaps):
                        if entry["url"] == child_url:
                            self.discovered_sitemaps[i]["parent"] = index_position
                            break
    
    def get_sitemap_info(self, sitemap_url: str) -> Dict[str, Any]:
        """
        Récupère des informations détaillées sur un sitemap (nombre d'URLs, etc.)
        """
        info = {
            "url": sitemap_url,
            "url_count": 0,
            "last_modified": None
        }
        
        try:
            response = self.session.get(sitemap_url, timeout=Config.TIMEOUT)
            if response.status_code != 200:
                return info
                
            root = ET.fromstring(response.content)
            
            # Détecter le namespace
            ns = None
            if root.tag.startswith('{'):
                ns_end = root.tag.find('}')
                if ns_end >= 0:
                    ns = {'ns': root.tag[1:ns_end]}
            
            # Compter les URLs
            if ns:
                urls = root.findall('.//ns:url', ns)
                info["url_count"] = len(urls)
                
                # Chercher la dernière date de modification
                lastmods = root.findall('.//ns:lastmod', ns)
                if lastmods:
                    dates = [lm.text for lm in lastmods if lm.text]
                    if dates:
                        info["last_modified"] = max(dates)
            else:
                urls = root.findall('.//url')
                info["url_count"] = len(urls)
                
                # Chercher la dernière date de modification
                lastmods = root.findall('.//lastmod')
                if lastmods:
                    dates = [lm.text for lm in lastmods if lm.text]
                    if dates:
                        info["last_modified"] = max(dates)
                
        except Exception:
            pass
            
        return info