import streamlit as st
import pandas as pd
from io import StringIO
import time
import logging
import re
from ..utils import sanitize_html

# Configuration du logger
logger = logging.getLogger('history_tab')

def sanitize_history_data(data):
    """Sanitize les données d'historique pour éviter les attaques XSS."""
    if isinstance(data, dict):
        sanitized_data = {}
        for key, value in data.items():
            sanitized_data[key] = sanitize_history_data(value)
        return sanitized_data
    elif isinstance(data, list):
        return [sanitize_history_data(item) for item in data]
    elif isinstance(data, str):
        # Sanitize les chaînes de caractères
        return sanitize_html(data)
    else:
        return data

def save_to_history(results, input_urls, parameters, execution_time):
    """Sauvegarde une extraction dans l'historique de manière sécurisée."""
    try:
        # Validation des entrées
        if not isinstance(results, list) or not isinstance(input_urls, list):
            logger.error("Invalid data format for history entry")
            return
            
        # Limiter le nombre d'entrées d'historique pour éviter les problèmes de mémoire
        max_history_entries = 100
        if 'history' in st.session_state and len(st.session_state.history) >= max_history_entries:
            # Supprimer l'entrée la plus ancienne
            st.session_state.history.pop(0)
            
        # Sanitize les données avant stockage
        sanitized_results = sanitize_history_data(results)
        sanitized_urls = sanitize_history_data(input_urls)
        
        history_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "input_urls": sanitized_urls,
            "nb_input_urls": len(input_urls),
            "nb_iframes_found": len(results),
            "results": sanitized_results,
            "parameters": parameters,
            "execution_time": execution_time
        }
        
        # Vérifier si l'historique existe déjà
        if 'history' not in st.session_state:
            st.session_state.history = []
            
        st.session_state.history.append(history_entry)
        logger.info(f"Added history entry with {len(results)} results")
    except Exception as e:
        logger.error(f"Error saving to history: {str(e)}")

def display_history_entry(entry, idx):
    """Affiche les détails d'une entrée de l'historique de manière sécurisée."""
    try:
        st.markdown("### Extraction details")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("URLs analyzed", entry["nb_input_urls"])
        with col2:
            st.metric("Iframes found", entry["nb_iframes_found"])
        with col3:
            st.metric("Duration", f"{entry['execution_time']:.2f}s")

        st.markdown("#### Parameters")
        # Afficher uniquement les paramètres approuvés
        safe_params = {
            k: v for k, v in entry["parameters"].items() 
            if k in ["test_mode", "test_urls", "workers", "timeout", "chunk_size"]
        }
        st.json(safe_params)

        st.markdown("#### Source URLs")
        # Limiter le nombre d'URLs affichées
        max_urls_display = 50
        display_urls = entry["input_urls"][:max_urls_display]
        if len(entry["input_urls"]) > max_urls_display:
            display_urls.append(f"... {len(entry['input_urls']) - max_urls_display} more URLs")
        st.write(display_urls)

        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("Reload this extraction", key=f"reload_{idx}"):
                # Validation avant chargement
                if isinstance(entry["results"], list) and all(isinstance(item, dict) for item in entry["results"]):
                    st.session_state.extraction_results = entry["results"]
                    st.success("✨ Extraction reloaded! You can now analyze it in the 'Analysis' tab")
                else:
                    st.error("Unable to reload this extraction due to invalid data format")

            # Export option with sanitized data
            if "results" in entry and isinstance(entry["results"], list) and len(entry["results"]) > 0:
                try:
                    output = StringIO()
                    df = pd.DataFrame(entry["results"])
                    df.to_csv(output, index=False)
                    st.download_button(
                        "📥 Download results (CSV)",
                        output.getvalue(),
                        f"extraction_results_{entry['timestamp'].replace(' ', '_').replace(':', '-')}.csv",
                        "text/csv"
                    )
                except Exception as e:
                    st.error(f"Error generating CSV: {str(e)}")
                    logger.error(f"Error in CSV export: {str(e)}")
    except Exception as e:
        st.error(f"Error displaying history entry: {str(e)}")
        logger.error(f"Error in display_history_entry: {str(e)}")

def display():
    """Affiche l'onglet historique de manière sécurisée."""
    if not st.session_state.history:
        st.info("No extractions have been performed yet.")
        return

    st.markdown("### Extraction history")

    # Validation des données d'historique
    try:
        # Création du tableau récapitulatif
        history_data = []
        for entry in reversed(st.session_state.history):
            # Validation des champs obligatoires
            if not all(k in entry for k in ["timestamp", "nb_input_urls", "nb_iframes_found", "execution_time", "parameters"]):
                continue
                
            history_data.append({
                "Date": entry["timestamp"],
                "Source URLs": entry["nb_input_urls"],
                "Iframes found": entry["nb_iframes_found"],
                "Duration (s)": f"{entry['execution_time']:.2f}",
                "Test mode": "✓" if entry["parameters"].get("test_mode", False) else "✗",
            })

        history_df = pd.DataFrame(history_data)
        st.dataframe(history_df, use_container_width=True)

        # Sélection d'une extraction pour voir les détails
        if history_data:  # Vérifier qu'il y a des données valides
            selected_idx = st.selectbox(
                "Select an extraction to view details",
                range(len(st.session_state.history)),
                format_func=lambda x: f"{st.session_state.history[-(x+1)]['timestamp']}"
            )

            if selected_idx is not None:
                display_history_entry(
                    st.session_state.history[-(selected_idx+1)], 
                    selected_idx
                )
        else:
            st.warning("No valid history entries found.")
    except Exception as e:
        st.error(f"Error displaying history: {str(e)}")
        logger.error(f"Error in display history: {str(e)}")