import streamlit as st
import pandas as pd
from io import StringIO, BytesIO
import time
import logging
import re
import json
from datetime import datetime
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
        
        # Compter les formulaires récupérés
        recovered_forms = [r for r in results if r.get('Recovery Status') == 'Recovered']
        original_forms = [r for r in results if r.get('Recovery Status') != 'Recovered']
        
        history_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "input_urls": sanitized_urls,
            "nb_input_urls": len(input_urls),
            "nb_iframes_found": len(results),
            "nb_recovered_forms": len(recovered_forms),
            "nb_original_forms": len(original_forms),
            "results": sanitized_results,
            "parameters": parameters,
            "execution_time": execution_time
        }
        
        # Sauvegarder les formulaires manquants s'ils existent
        if 'missing_forms' in st.session_state and st.session_state.missing_forms is not None:
            # Convertir en dict pour stockage dans l'historique
            history_entry["missing_forms"] = st.session_state.missing_forms.to_dict('records') if not st.session_state.missing_forms.empty else []
        
        # Sauvegarder les formulaires récupérés s'ils existent
        if 'recovered_forms' in st.session_state and st.session_state.recovered_forms:
            history_entry["recovered_forms"] = st.session_state.recovered_forms
        
        # Vérifier si l'historique existe déjà
        if 'history' not in st.session_state:
            st.session_state.history = []
            
        st.session_state.history.append(history_entry)
        logger.info(f"Added history entry with {len(results)} results ({len(recovered_forms)} recovered)")
    except Exception as e:
        logger.error(f"Error saving to history: {str(e)}")

def export_with_sheets(results, timestamp, missing_forms=None, recovered_forms=None):
    """Crée un export Excel multi-feuilles pour une entrée d'historique."""
    try:
        if not results or not isinstance(results, list):
            st.error("Invalid results format")
            return None, None
            
        # Créer le DataFrame principal
        export_df = pd.DataFrame(results)
        
        # Générer un timestamp unique pour le nom du fichier
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"history_export_{current_time}"
        
        # Créer le buffer de sortie
        output = BytesIO()
        
        # Créer un writer Excel
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Feuille 1: Résultats de l'extraction
            export_df.to_excel(writer, sheet_name="Extraction Results", index=False)
            
            # Feuille 2: Formulaires manquants (si disponibles)
            if missing_forms and len(missing_forms) > 0:
                missing_df = pd.DataFrame(missing_forms)
                missing_df.to_excel(writer, sheet_name="Missing Forms", index=False)
            
            # Feuille 3: Formulaires récupérés (si disponibles)
            if recovered_forms and len(recovered_forms) > 0:
                recovered_df = pd.DataFrame(recovered_forms)
                recovered_df.to_excel(writer, sheet_name="Recovered Forms", index=False)
            
            # Feuille 4: Données des templates Selligent
            try:
                # Charger les données de template depuis le fichier JSON
                with open("data/template_mapping.json", "r") as f:
                    template_data = json.load(f)
                    
                # Convertir en DataFrame
                template_df = pd.DataFrame([
                    {"Form ID": form_id, "Template Name": template_name}
                    for form_id, template_name in template_data.items()
                ])
                
                template_df.to_excel(writer, sheet_name="Template Data", index=False)
            except Exception as e:
                logger.error(f"Could not include template data: {str(e)}")
        
        output.seek(0)
        return output, filename
    except Exception as e:
        logger.error(f"Error creating multi-sheet export: {str(e)}")
        return None, None

def display_history_entry(entry, idx):
    """Affiche les détails d'une entrée de l'historique de manière sécurisée."""
    try:
        st.markdown("### Extraction details")

        # Afficher les métriques de base
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("URLs analyzed", entry["nb_input_urls"])
        with col2:
            st.metric("Iframes found", entry["nb_iframes_found"])
        with col3:
            st.metric("Duration", f"{entry['execution_time']:.2f}s")

        # Afficher les métriques pour les formulaires récupérés s'ils existent
        if "nb_recovered_forms" in entry and entry["nb_recovered_forms"] > 0:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Original forms", entry["nb_original_forms"])
            with col2:
                st.metric("Recovered forms", entry["nb_recovered_forms"], 
                         delta=f"+{entry['nb_recovered_forms']}", 
                         delta_color="normal")

        # Afficher les formulaires manquants s'ils existent
        if "missing_forms" in entry and entry["missing_forms"]:
            if "nb_recovered_forms" in entry and entry["nb_recovered_forms"] > 0:
                st.warning(f"⚠️ {len(entry['missing_forms']) - entry['nb_recovered_forms']} forms still missing after recovery attempts")
            else:
                st.warning(f"⚠️ {len(entry['missing_forms'])} forms found in URL mapping but missing in extraction")

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
                    
                    # Recharger aussi les formulaires manquants s'ils existent
                    if "missing_forms" in entry and entry["missing_forms"]:
                        st.session_state.missing_forms = pd.DataFrame(entry["missing_forms"])
                    else:
                        st.session_state.missing_forms = None
                    
                    # Recharger les formulaires récupérés s'ils existent
                    if "recovered_forms" in entry and entry["recovered_forms"]:
                        st.session_state.recovered_forms = entry["recovered_forms"]
                    else:
                        st.session_state.recovered_forms = None
                    
                    st.success("✨ Extraction reloaded! You can now analyze it in the 'Analysis' tab")
                else:
                    st.error("Unable to reload this extraction due to invalid data format")

            # Options d'export
            st.markdown("#### Export Options")
            export_format = st.radio(
                "Export format", 
                ["CSV", "Excel (multi-sheet)"],
                key=f"export_format_{idx}"
            )

            # Export option with sanitized data
            if "results" in entry and isinstance(entry["results"], list) and len(entry["results"]) > 0:
                try:
                    if export_format == "CSV":
                        output = StringIO()
                        df = pd.DataFrame(entry["results"])
                        df.to_csv(output, index=False)
                        st.download_button(
                            "📥 Download results (CSV)",
                            output.getvalue(),
                            f"extraction_results_{entry['timestamp'].replace(' ', '_').replace(':', '-')}.csv",
                            "text/csv",
                            key=f"download_csv_{idx}"
                        )
                    else:  # Excel multi-sheet
                        # Récupérer les formulaires manquants pour l'export
                        missing_forms = entry.get("missing_forms", [])
                        
                        # Récupérer les formulaires récupérés pour l'export
                        recovered_forms = entry.get("recovered_forms", [])
                        
                        output, filename = export_with_sheets(
                            entry["results"], 
                            entry["timestamp"],
                            missing_forms,
                            recovered_forms
                        )
                        
                        if output:
                            st.download_button(
                                "📥 Download results (Excel)",
                                output.getvalue(),
                                f"{filename}.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"download_excel_{idx}"
                            )
                except Exception as e:
                    st.error(f"Error generating export: {str(e)}")
                    logger.error(f"Error in export: {str(e)}")
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
                
            # Calculer le nombre de formulaires manquants
            missing_forms_count = len(entry.get("missing_forms", [])) if "missing_forms" in entry else 0
            
            # Calculer le nombre de formulaires récupérés
            recovered_forms_count = entry.get("nb_recovered_forms", 0)
            
            history_data.append({
                "Date": entry["timestamp"],
                "Source URLs": entry["nb_input_urls"],
                "Iframes found": entry["nb_iframes_found"],
                "Missing forms": missing_forms_count,
                "Recovered forms": recovered_forms_count,
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