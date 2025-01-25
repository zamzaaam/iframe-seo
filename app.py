import streamlit as st
import requests
from bs4 import BeautifulSoup
import csv
import pandas as pd
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple
import time
import xml.etree.ElementTree as ET
import re

# Configuration
MAX_WORKERS = 10
TIMEOUT = 5
CHUNK_SIZE = 50

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
            
    except Exception as e:
        st.warning(f"Erreur pour {url}: {str(e)}")
        return []

def extract_urls_from_sitemap(sitemap_url: str) -> List[str]:
    """Extrait les URLs d'un sitemap."""
    try:
        session = create_session()
        response = session.get(sitemap_url, timeout=TIMEOUT)
        if response.status_code != 200:
            return []
        
        root = ET.fromstring(response.content)
        ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
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

def analyze_crm_data(results: List[Dict], mapping_data: pd.DataFrame = None) -> pd.DataFrame:
    """Analyse les données CRM et applique le mapping si disponible."""
    df = pd.DataFrame(results)
    
    if mapping_data is not None:
        # Fusion avec le mapping
        df = df.merge(
            mapping_data,
            left_on='Form ID',
            right_on='ID',
            how='left'
        )
        
        # Mise à jour des codes CRM manquants
        mask = df['CRM Campaign'].isna()
        if 'CRM_CAMPAIGN' in df.columns:
            df.loc[mask, 'CRM Campaign'] = df.loc[mask, 'CRM_CAMPAIGN']
        
        # Nettoyage des colonnes
        df = df.drop(['ID'], axis=1, errors='ignore')
    
    return df

def main():
    st.set_page_config(
        page_title="Extracteur d'iframes avec analyse CRM",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("Extraction et analyse des iframes")
    
    # Initialisation des variables de session
    if 'extraction_results' not in st.session_state:
        st.session_state.extraction_results = None
    if 'analyzed_results' not in st.session_state:
        st.session_state.analyzed_results = None
    
    # Interface principale
    tabs = st.tabs(["Extraction", "Analyse CRM"])
    
    with tabs[0]:
        st.markdown("""
        Cette application extrait les iframes du chemin `//body/div/div/main/` 
        qui commencent par `https://ovh.slgnt.eu/optiext/`.
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
                
                # Mode test
                test_mode = st.checkbox("Activer le mode test", False)
                test_urls = None
                if test_mode:
                    test_urls = st.number_input(
                        "Nombre d'URLs à tester",
                        min_value=1,
                        max_value=1000,
                        value=10,
                        help="Limite le nombre d'URLs à traiter pour les tests"
                    )
                
                # Autres paramètres
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
                    
                # Application du mode test si activé
                if test_mode and test_urls and len(processed_urls) > test_urls:
                    processed_urls = processed_urls[:test_urls]
                    st.info(f"🧪 Mode test activé : traitement limité aux {test_urls} premières URLs")

                # Traitement des URLs
                if processed_urls:
                    status = st.empty()
                    progress = st.progress(0)
                    status.write(f"🔍 Analyse de {len(processed_urls)} URLs...")
                    
                    for i in range(0, len(processed_urls), CHUNK_SIZE):
                        chunk = processed_urls[i:i + CHUNK_SIZE]
                        status.write(f"🔍 Traitement du lot {i//CHUNK_SIZE + 1}/{len(processed_urls)//CHUNK_SIZE + 1}")
                        chunk_results = process_urls_batch(chunk, progress)
                        results.extend(chunk_results)

                    if results:
                        st.session_state.extraction_results = results
                        execution_time = time.time() - start_time
                        
                        st.success(f"""
                        ✨ Extraction terminée en {execution_time:.2f} secondes !
                        - 📊 {len(processed_urls)} URLs analysées
                        - 🎯 {len(results)} iframes trouvés
                        """)
                        
                        with st.expander("📋 Voir les résultats bruts"):
                            st.dataframe(results)
                    else:
                        st.info("ℹ️ Aucun iframe trouvé.")
    
    with tabs[1]:
        if st.session_state.extraction_results:
            st.markdown("### Analyse des codes CRM")
            
            mapping_file = st.file_uploader(
                "Charger le fichier de mapping (optionnel)",
                type=['xlsx']
            )
            
            if st.button("Analyser les données CRM", type="primary"):
                with st.spinner("🔄 Analyse en cours..."):
                    mapping_data = None
                    if mapping_file:
                        try:
                            mapping_data = pd.read_excel(mapping_file)
                            st.success(f"✅ Fichier de mapping chargé : {len(mapping_data)} entrées")
                        except Exception as e:
                            st.error(f"❌ Erreur de chargement du mapping : {str(e)}")
                    
                    analyzed_df = analyze_crm_data(
                        st.session_state.extraction_results,
                        mapping_data
                    )
                    
                    st.session_state.analyzed_results = analyzed_df
                    
                    # Statistiques
                    total_forms = len(analyzed_df)
                    forms_with_id = analyzed_df['Form ID'].notna().sum()
                    forms_with_crm = analyzed_df['CRM Campaign'].notna().sum()
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total des formulaires", total_forms)
                    with col2:
                        st.metric("Formulaires avec ID", forms_with_id)
                    with col3:
                        st.metric("Formulaires avec code CRM", forms_with_crm)
                    
                    # Filtres
                    st.markdown("### Filtres")
                    col1, col2 = st.columns(2)
                    with col1:
                        filter_id = st.text_input("Filtrer par ID")
                    with col2:
                        filter_crm = st.text_input("Filtrer par code CRM")
                    
                    filtered_df = analyzed_df.copy()
                    if filter_id:
                        filtered_df = filtered_df[
                            filtered_df['Form ID'].fillna('').str.contains(filter_id, case=False)
                        ]
                    if filter_crm:
                        filtered_df = filtered_df[
                            filtered_df['CRM Campaign'].fillna('').str.contains(filter_crm, case=False)
                        ]
                    
                    # Affichage des résultats
                    st.markdown("### Résultats de l'analyse")
                    st.dataframe(filtered_df)
                    
                    # Export
                    output = StringIO()
                    filtered_df.to_csv(output, index=False)
                    st.download_button(
                        "📥 Télécharger les résultats (CSV)",
                        output.getvalue(),
                        "resultats_analyse_crm.csv",
                        "text/csv"
                    )
        else:
            st.info("ℹ️ Veuillez d'abord extraire des iframes dans l'onglet Extraction.")

if __name__ == "__main__":
    main()