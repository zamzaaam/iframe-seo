import streamlit as st
import pandas as pd
from io import StringIO
import time

def save_to_history(results, input_urls, parameters, execution_time):
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

def display_history_entry(entry, idx):
    """Affiche les détails d'une entrée de l'historique."""
    st.markdown("### Extraction details")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("URLs analyzed", entry["nb_input_urls"])
    with col2:
        st.metric("Iframes found", entry["nb_iframes_found"])
    with col3:
        st.metric("Duration", f"{entry['execution_time']:.2f}s")

    st.markdown("#### Parameters")
    params = entry["parameters"]
    st.json(params)

    st.markdown("#### Source URLs")
    st.write(entry["input_urls"])

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Reload this extraction", key=f"reload_{idx}"):
            st.session_state.extraction_results = entry["results"]
            st.success("✨ Extraction reloaded! You can now analyze it in the 'Analysis' tab")

        # Export option
        output = StringIO()
        df = pd.DataFrame(entry["results"])
        df.to_csv(output, index=False)
        st.download_button(
            "📥 Download results (CSV)",
            output.getvalue(),
            f"extraction_results_{entry['timestamp'].replace(' ', '_')}.csv",
            "text/csv"
        )

def display():
    """Affiche l'onglet historique."""
    if not st.session_state.history:
        st.info("No extractions have been performed yet.")
        return

    st.markdown("### Extraction history")

    # Création du tableau récapitulatif
    history_data = []
    for entry in reversed(st.session_state.history):
        history_data.append({
            "Date": entry["timestamp"],
            "Source URLs": entry["nb_input_urls"],
            "Iframes found": entry["nb_iframes_found"],
            "Duration (s)": f"{entry['execution_time']:.2f}",
            "Test mode": "✓" if entry["parameters"]["test_mode"] else "✗",
        })

    history_df = pd.DataFrame(history_data)
    st.dataframe(history_df, use_container_width=True)

    # Sélection d'une extraction pour voir les détails
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
