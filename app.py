# Iframe SEO Analyzer - Main Application

import streamlit as st
import time

from src.config import Config
from src.ui import initialize_session_state, get_app_configuration
from src.ui import extraction_tab, analysis_tab, history_tab, share_tab

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