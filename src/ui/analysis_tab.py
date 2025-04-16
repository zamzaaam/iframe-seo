import streamlit as st
import pandas as pd
from ..analysis import IframeAnalyzer
from io import StringIO, BytesIO

def display():
    if not st.session_state.extraction_results:
        st.info("ℹ️ Please extract iframes first in the Extraction tab.")
        return

    st.header("🔍 Form Analysis", divider="rainbow")
    
    total_forms = len(st.session_state.extraction_results)
    extraction_time = st.session_state.history[-1]["timestamp"] if st.session_state.history else "Unknown"
    st.caption(f"Last extraction: {extraction_time} ({total_forms} forms found)")

    # Ajouter un avertissement si l'analyse n'est pas à jour
    if st.session_state.analyzed_df is not None and st.session_state.history:
        last_extraction = st.session_state.history[-1]["results"]
        if last_extraction != st.session_state.extraction_results:
            st.warning("⚠️ New extraction detected! Please restart the analysis to see the latest results.")
            if st.button("🔄 Update analysis"):
                st.session_state.analyzed_df = None
                st.rerun()
            return

    with st.sidebar:
        st.subheader("⚙️ Analysis Configuration")
        use_mapping = st.toggle("Use external mapping file", value=False)
        
        mapping_data = None
        selected_columns = []
        
        if use_mapping:
            mapping_file = st.file_uploader(
                "Import mapping file (Excel/CSV)",
                type=['xlsx', 'csv']
            )
            
            if mapping_file:
                try:
                    if mapping_file.name.endswith('.csv'):
                        mapping_data = pd.read_csv(mapping_file)
                    else:
                        mapping_data = pd.read_excel(mapping_file)
                    
                    st.success(f"✅ File loaded with {len(mapping_data)} rows")
                    
                    # Afficher un aperçu du fichier
                    with st.expander("📊 Preview imported data"):
                        st.dataframe(mapping_data.head(), use_container_width=True)
                    
                    # Sélection de la colonne ID
                    id_column = st.selectbox(
                        "Select the column containing Form IDs",
                        options=mapping_data.columns.tolist(),
                        index=mapping_data.columns.get_loc('ID') if 'ID' in mapping_data.columns else 0,
                        help="Choose the column that contains your form identifiers"
                    )
                    
                    # Sélection des colonnes additionnelles
                    other_columns = [col for col in mapping_data.columns if col != id_column]
                    selected_columns = st.multiselect(
                        "Select additional columns to import",
                        options=other_columns,
                        default=['CRM_CAMPAIGN'] if 'CRM_CAMPAIGN' in other_columns else []
                    )
                    
                    st.info(f"📌 Selected {len(selected_columns)} column(s) to import")
                    
                except Exception as e:
                    st.error(f"❌ Error loading file: {str(e)}")
                    mapping_data = None

    if st.session_state.analyzed_df is None:
        st.warning("⚠️ Click 'Start analysis' to begin")
        col1, _ = st.columns([1, 3])
        with col1:
            if st.button("📊 Start analysis", type="primary"):
                with st.spinner("Analyzing..."):
                    analyzer = IframeAnalyzer()
                    analyzed_df = analyzer.analyze_crm_data(
                        st.session_state.extraction_results,
                        mapping_data,
                        selected_columns,
                        id_column
                    )
                    st.session_state.analyzed_df = analyzed_df
                    st.rerun()
        return

    # Display tabs
    summary_tab, details_tab, export_tab = st.tabs([
        "📈 Summary", "🔎 Details", "💾 Export"
    ])

    with summary_tab:
        display_summary(st.session_state.analyzed_df)

    with details_tab:
        display_details(st.session_state.analyzed_df)

    with export_tab:
        display_export(st.session_state.analyzed_df)

    with st.sidebar:
        if st.button("🔄 Reset analysis"):
            st.session_state.analyzed_df = None
            st.rerun()

def display_summary(df):
    total_forms = len(df)
    total_unique = df['Form ID'].nunique()
    templated = df[df['Template'].notna()]['Form ID'].nunique() if 'Template' in df.columns else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total forms", total_forms)
    with col2:
        st.metric("Unique forms", total_unique)
    with col3:
        st.metric("With CRM code", df['CRM Campaign'].notna().sum())
    with col4:
        st.metric("Without CRM code", df['CRM Campaign'].isna().sum())

    # Afficher les métriques pour les colonnes importées
    imported_columns = [col for col in df.columns if col not in ['URL source', 'Iframe', 'Form ID', 'CRM Campaign', 'Template']]
    if imported_columns:
        st.subheader("📊 Imported data metrics")
        metrics_cols = st.columns(min(4, len(imported_columns)))
        
        for idx, col_name in enumerate(imported_columns):
            with metrics_cols[idx % 4]:
                filled_values = df[col_name].notna().sum()
                st.metric(
                    f"{col_name}",
                    f"{filled_values}/{total_forms}",
                    help=f"Number of forms with {col_name} information"
                )

    display_alerts(df)

def display_details(df):
    st.subheader("📑 Detailed data")
    
    # Filtres standard
    filter_cols = st.columns([1, 1])
    with filter_cols[0]:
        template_filter = st.multiselect(
            "Filter by template",
            options=df['Template'].dropna().unique() if 'Template' in df.columns else []
        )
    with filter_cols[1]:
        crm_filter = st.radio(
            "CRM status",
            ["All", "With CRM", "Without CRM"]
        )
    
    # Filtres pour les colonnes importées
    imported_columns = [col for col in df.columns if col not in ['URL source', 'Iframe', 'Form ID', 'CRM Campaign', 'Template']]
    imported_filters = {}
    
    if imported_columns:
        st.subheader("🔍 Filter by imported data")
        filter_columns = st.columns(min(3, len(imported_columns)))
        
        for idx, col_name in enumerate(imported_columns):
            with filter_columns[idx % 3]:
                # Obtenir les valeurs uniques en excluant les NaN
                unique_values = df[col_name].dropna().unique()
                if len(unique_values) > 0 and len(unique_values) <= 10:  # Seulement pour les colonnes avec un nombre raisonnable de valeurs uniques
                    imported_filters[col_name] = st.multiselect(
                        f"Filter by {col_name}",
                        options=unique_values
                    )

    filtered_df = apply_filters(df, template_filter, crm_filter, imported_filters)
    st.metric("Filtered results", len(filtered_df))
    st.dataframe(
        filtered_df,
        use_container_width=True,
        column_config={"URL source": st.column_config.LinkColumn()}
    )

def display_export(df):
    st.subheader("💾 Export results")
    
    export_format = st.radio("Export format", ["CSV", "Excel"])
    col1, _ = st.columns([1, 3])
    
    with col1:
        if export_format == "CSV":
            output = StringIO()
            df.to_csv(output, index=False)
            st.download_button(
                "📥 Download analysis (CSV)",
                output.getvalue(),
                "forms_analysis.csv",
                "text/csv"
            )
        else:
            output = BytesIO()
            df.to_excel(output, engine='openpyxl', index=False)
            output.seek(0)
            st.download_button(
                "📥 Download analysis (Excel)",
                output.getvalue(),
                "forms_analysis.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

def display_alerts(df):
    st.subheader("⚠️ Points of attention", divider="red")
    alerts = []
    
    bad_integration = df[df['Iframe'].str.contains("survey.dll", na=False)]
    missing_crm = df[df['CRM Campaign'].isna()]
    
    if not bad_integration.empty:
        alerts.append({
            "severity": "error",
            "title": "Bad integrations",
            "message": f"{len(bad_integration)} forms with incorrect integration detected",
            "data": bad_integration[['URL source', 'Form ID', 'CRM Campaign']]
        })

    if not missing_crm.empty:
        alerts.append({
            "severity": "warning",
            "title": "Missing CRM codes",
            "message": f"{len(missing_crm)} forms without CRM code",
            "data": missing_crm[['URL source', 'Form ID']]
        })
    
    # Alertes pour les colonnes importées
    imported_columns = [col for col in df.columns if col not in ['URL source', 'Iframe', 'Form ID', 'CRM Campaign', 'Template']]
    for col_name in imported_columns:
        missing_data = df[df[col_name].isna()]
        if not missing_data.empty:
            alerts.append({
                "severity": "info",
                "title": f"Missing {col_name}",
                "message": f"{len(missing_data)} forms without {col_name} information",
                "data": missing_data[['URL source', 'Form ID']]
            })

    if alerts:
        for alert in alerts:
            with st.expander(f"🔔 {alert['title']}"):
                if alert['severity'] == "error":
                    st.error(alert['message'])
                elif alert['severity'] == "warning":
                    st.warning(alert['message'])
                else:
                    st.info(alert['message'])
                st.dataframe(
                    alert['data'],
                    use_container_width=True,
                    column_config={"URL source": st.column_config.LinkColumn()}
                )
    else:
        st.success("✅ No anomalies detected")

def apply_filters(df, template_filter, crm_filter, imported_filters=None):
    filtered_df = df.copy()
    
    # Appliquer les filtres standard
    if template_filter:
        filtered_df = filtered_df[filtered_df['Template'].isin(template_filter)]
    
    if crm_filter == "With CRM":
        filtered_df = filtered_df[filtered_df['CRM Campaign'].notna()]
    elif crm_filter == "Without CRM":
        filtered_df = filtered_df[filtered_df['CRM Campaign'].isna()]
    
    # Appliquer les filtres pour les colonnes importées
    if imported_filters:
        for col_name, filter_values in imported_filters.items():
            if filter_values:  # Si des filtres sont sélectionnés
                filtered_df = filtered_df[filtered_df[col_name].isin(filter_values)]
    
    return filtered_df