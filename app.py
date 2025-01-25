import streamlit as st
import requests
from bs4 import BeautifulSoup
import csv
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import time
import xml.etree.ElementTree as ET

# Configuration
MAX_WORKERS = 10  # Nombre de threads simultanés
TIMEOUT = 5  # Timeout réduit pour les requêtes
CHUNK_SIZE = 50  # Nombre d'URLs à traiter par lot

def create_session():
    """Crée une session avec des paramètres optimisés."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    return session

def extract_iframe_links(session: requests.Session, url: str) -> List[Dict]:
    """Extrait les liens iframe d'une URL donnée."""
    try:
        response = session.get(url, timeout=TIMEOUT)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, "html.parser")
        try:
            main_section = soup.find("body").find("div").find("div").find("main")
            if not main_section:
                return []
                
            return [
                {"URL source": url, "Iframe": src}
                for iframe in main_section.find_all("iframe")
                if (src := iframe.get("src", "")).startswith("https://ovh.slgnt.eu/optiext/")
            ]
        except AttributeError:
            return []
            
    except Exception as e:
        st.warning(f"Erreur pour {url}: {str(e)}")
        return []

def extract_urls_from_sitemap(sitemap_url: str) -> List[str]:
    """Extrait les URLs d'un sitemap en utilisant xml.etree."""
    try:
        session = create_session()
        response = session.get(sitemap_url, timeout=TIMEOUT)
        if response.status_code != 200:
            return []
        
        # Parse le XML avec ElementTree
        root = ET.fromstring(response.content)
        
        # L'espace de noms par défaut pour les sitemaps
        ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # Extraction des URLs en tenant compte de l'espace de noms
        urls = [loc.text for loc in root.findall('.//ns:loc', ns)]
        return urls
            
    except Exception as e:
        st.warning(f"Erreur avec le sitemap {sitemap_url}: {str(e)}")
        return []

def process_urls_batch(urls: List[str], progress_bar) -> List[Dict]:
    """Traite un lot d'URLs en parallèle."""
    results = []
    session = create_session()
    completed_urls = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {
            executor.submit(extract_iframe_links, session, url): url 
            for url in urls
        }
        
        for future in as_completed(future_to_url):
            url_results = future.result()
            if url_results:
                results.extend(url_results)
            completed_urls += 1
            progress_bar.progress(completed_urls / len(urls))
            
    return results

def main():
    st.set_page_config(
        page_title="Extracteur d'iframes OVH",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("Extraction des liens d'iframes OVH")
    st.markdown("""
    Cette application extrait les iframes du chemin `//body/div/div/main/` qui commencent par `https://ovh.slgnt.eu/optiext/`.
    
    *Version optimisée avec multithreading*
    """)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        input_type = st.radio(
            "Type d'entrée :",
            ["Sitemaps XML", "Liste d'URLs"]
        )

        if input_type == "Sitemaps XML":
            urls_input = st.text_area(
                "URLs des sitemaps (une par ligne) :",
                placeholder="https://example.com/sitemap.xml",
                height=200
            )
        else:
            urls_input = st.text_area(
                "URLs à analyser (une par ligne) :",
                placeholder="https://example.com/page1",
                height=200
            )

    with col2:
        st.markdown("### Configuration")
        with st.expander("Paramètres avancés"):
            global MAX_WORKERS, TIMEOUT, CHUNK_SIZE
            MAX_WORKERS = st.slider("Nombre de workers", 1, 20, 10)
            TIMEOUT = st.slider("Timeout (secondes)", 1, 15, 5)
            CHUNK_SIZE = st.slider("Taille des lots", 10, 100, 50)

    urls = [url.strip() for url in urls_input.splitlines() if url.strip()]

    if st.button("Extraire les iframes", type="primary"):
        if not urls:
            st.warning("⚠️ Veuillez entrer au moins une URL.")
            return

        with st.spinner("🔄 Traitement en cours..."):
            start_time = time.time()
            results = []
            processed_urls = []

            # Traitement des sitemaps
            if input_type == "Sitemaps XML":
                status_sitemap = st.empty()
                progress_sitemap = st.progress(0)
                
                for idx, sitemap_url in enumerate(urls):
                    status_sitemap.write(f"📑 Lecture du sitemap: {sitemap_url}")
                    sitemap_urls = extract_urls_from_sitemap(sitemap_url)
                    processed_urls.extend(sitemap_urls)
                    progress_sitemap.progress((idx + 1) / len(urls))
                
                if processed_urls:
                    st.success(f"✅ {len(processed_urls)} URLs extraites des sitemaps")
                else:
                    st.error("❌ Aucune URL trouvée dans les sitemaps")
                    return
            else:
                processed_urls = urls

            # Traitement des URLs par lots
            if processed_urls:
                status = st.empty()
                progress = st.progress(0)
                status.write(f"🔍 Analyse de {len(processed_urls)} URLs...")
                
                # Traitement par lots
                for i in range(0, len(processed_urls), CHUNK_SIZE):
                    chunk = processed_urls[i:i + CHUNK_SIZE]
                    status.write(f"🔍 Traitement du lot {i//CHUNK_SIZE + 1}/{len(processed_urls)//CHUNK_SIZE + 1}")
                    chunk_results = process_urls_batch(chunk, progress)
                    results.extend(chunk_results)

                # Préparation des résultats
                if results:
                    # Déduplication et comptage
                    unique_results = {}
                    for result in results:
                        key = (result["URL source"], result["Iframe"])
                        if key not in unique_results:
                            unique_results[key] = result

                    final_results = list(unique_results.values())

                    # Compter les occurrences
                    iframe_counts = {}
                    for result in final_results:
                        iframe_counts[result["Iframe"]] = iframe_counts.get(result["Iframe"], 0) + 1

                    # Ajouter le comptage
                    for result in final_results:
                        result["Occurrences"] = iframe_counts[result["Iframe"]]

                    # Export CSV
                    output = StringIO()
                    writer = csv.DictWriter(output, fieldnames=["URL source", "Iframe", "Occurrences"])
                    writer.writeheader()
                    writer.writerows(final_results)
                    
                    execution_time = time.time() - start_time
                    
                    st.success(f"""
                    ✨ Extraction terminée en {execution_time:.2f} secondes !
                    - 📊 {len(processed_urls)} URLs analysées
                    - 🎯 {len(final_results)} iframes uniques trouvés
                    """)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button(
                            "📥 Télécharger les résultats (CSV)",
                            output.getvalue(),
                            "resultats_iframes.csv",
                            "text/csv"
                        )
                    
                    with st.expander("📋 Voir les résultats"):
                        st.table(final_results)
                else:
                    st.info("ℹ️ Aucun iframe trouvé.")

if __name__ == "__main__":
    main()