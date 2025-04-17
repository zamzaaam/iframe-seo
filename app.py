# Modifications à apporter à app.py

import streamlit as st
import pandas as pd
from io import StringIO, BytesIO
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

from src.config import Config
from src.extractors import SitemapExtractor, IframeExtractor
from src.analysis import IframeAnalyzer
from src.ui import initialize_session_state, get_app_configuration
from src.ui import extraction_tab, analysis_tab, history_tab, share_tab

def process_urls_batch(urls: List[str], progress_bar) -> List[Dict]:
    """Traite un lot d'URLs en parallèle."""
    results = []
    extractor = IframeExtractor()
    completed_urls = 0

    # Vérifier l'état d'arrêt avant de commencer le traitement
    if st.session_state.abort_extraction:
        progress_bar.progress(1.0)  # Compléter la barre de progression
        return results

    with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
        future_to_url = {
            executor.submit(extractor.extract_from_url, url): url
            for url in urls
        }

        for future in as_completed(future_to_url):
            # Vérifier si l'extraction doit être interrompue
            if st.session_state.abort_extraction:
                # Annuler les futures en attente
                for f in future_to_url:
                    f.cancel()
                break
            
            url_results = future.result()
            if url_results:
                results.extend(url_results)
            completed_urls += 1
            progress_bar.progress(completed_urls / len(urls))

    return results

def save_to_history(results: List[Dict], input_urls: List[str], parameters: Dict, execution_time: float):
    """Sauvegarde une extraction dans l'historique."""
    history_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "input_urls": input_urls,
        "nb_input_urls": len(input_urls),
        "nb_iframes_found": len(results),
        "results": results,
        "parameters": parameters,
        "execution_time": execution_time
    }
    st.session_state.history.append(history_entry)

def main():
    st.set_page_config(
        page_title="iframe Form Extractor with CRM Analysis",
        page_icon="🔍",
        layout="wide"
    )

    initialize_session_state()

    # Initialiser la variable d'état pour l'arrêt d'urgence
    if 'abort_extraction' not in st.session_state:
        st.session_state.abort_extraction = False

    # Ajouter le bouton d'arrêt d'urgence dans la barre latérale
    with st.sidebar:
        st.markdown("## ⚠️ Emergency Controls")
        if st.button("🛑 STOP ALL EXTRACTIONS", 
                    type="primary", 
                    help="Immediately stops all running extractions",
                    use_container_width=True):
            st.session_state.abort_extraction = True
            st.warning("⚠️ Extraction abort requested. Please wait for current operations to finish...")
            # On utilisera un timer pour réinitialiser la variable d'état après un certain temps
            st.session_state.abort_requested_time = time.time()
    
    # Vérifier si un arrêt a été demandé il y a plus de 5 secondes et réinitialiser
    if 'abort_requested_time' in st.session_state and time.time() - st.session_state.abort_requested_time > 5:
        st.session_state.abort_extraction = False
        if 'abort_requested_time' in st.session_state:
            del st.session_state.abort_requested_time
    
    # Update configuration from UI
    config = get_app_configuration()
    Config.update(**config)

    # Main navigation
    tabs = st.tabs(["Extraction", "Analysis", "History", "Share"])

    with tabs[0]:
        extraction_tab.display()
    with tabs[1]:
        analysis_tab.display()
    with tabs[2]:
        history_tab.display()
    with tabs[3]:
        share_tab.display()

if __name__ == "__main__":
    main()