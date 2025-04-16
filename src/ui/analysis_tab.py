import streamlit as st
import pandas as pd
from ..analysis import IframeAnalyzer
from io import StringIO, BytesIO
from typing import Dict

def display_mapping_configuration(mapping_data: pd.DataFrame) -> Dict:
    """Configure le mapping des données importées."""
    st.subheader("🔗 Mapping Configuration")

    # Affichage de l'aperçu des données
    with st.expander("📊 Preview imported data", expanded=True):
        st.dataframe(mapping_data.head(), use_container_width=True)

    # Configuration des colonnes de mapping
    st.info("Select the columns to use for matching data:")
    
    col1, col2 = st.columns(2)
    with col1:
        url_column = st.selectbox(
            "URL column in imported file",
            options=mapping_data.columns.tolist(),
            help="Column containing the source URLs"
        )
    
    with col2:
        id_column = st.selectbox(
            "Form ID column in imported file",
            options=mapping_data.columns.tolist(),
            help="Column containing the form identifiers"
        )

    # Sélection des colonnes additionnelles
    additional_columns = [
        col for col in mapping_data.columns 
        if col not in [url_column, id_column]
    ]
    
    selected_columns = st.multiselect(
        "Select additional information to include",
        options=additional_columns,
        help="Choose which additional columns to include in the analysis"
    )

    # Validation du mapping
    if st.button("✅ Validate mapping", type="primary"):
        # Vérification des données
        missing_urls = mapping_data[url_column].isna().sum()
        missing_ids = mapping_data[id_column].isna().sum()
        
        if missing_urls > 0 or missing_ids > 0:
            st.warning(f"""
                ⚠️ Found missing values:
                - URLs: {missing_urls} missing
                - Form IDs: {missing_ids} missing
            """)

        return {
            "url_column": url_column,
            "id_column": id_column,
            "selected_columns": selected_columns
        }
    
    return None

def display():
    st.header("📊 Analysis", divider="rainbow")

    # Vérifie si des résultats sont disponibles
    if not st.session_state.extraction_results:
        st.info("ℹ️ Please extract data first in the Extraction tab.")
        return

    # Configuration du mapping
    with st.sidebar:
        st.subheader("🔄 Data Mapping")
        mapping_file = st.file_uploader(
            "Import additional data (Excel/CSV)",
            type=['xlsx', 'csv'],
            help="Import a file containing additional information to merge with the results"
        )

        if mapping_file:
            try:
                # Chargement du fichier avec détection du séparateur
                if mapping_file.name.endswith('.csv'):
                    # Essayer d'abord avec le séparateur point-virgule
                    try:
                        mapping_data = pd.read_csv(mapping_file, sep=';')
                    except:
                        # Si ça échoue, essayer avec la virgule
                        mapping_file.seek(0)  # Remettre le curseur au début du fichier
                        mapping_data = pd.read_csv(mapping_file, sep=',')
                else:
                    mapping_data = pd.read_excel(mapping_file)
                
                # Vérifier que le DataFrame n'est pas vide
                if mapping_data.empty:
                    st.error("❌ The imported file appears to be empty")
                    return
                    
                if len(mapping_data.columns) <= 1:
                    st.error("❌ File format error: Could not properly detect columns. Please check the file separator")
                    return
                    
                st.success(f"✅ File loaded with {len(mapping_data)} rows and {len(mapping_data.columns)} columns")
                
                # Aperçu des données
                with st.expander("📊 Preview imported data", expanded=True):
                    st.dataframe(mapping_data.head())
                    st.caption("Detected columns: " + ", ".join(mapping_data.columns.tolist()))

                # Configuration des colonnes de mapping
                mapping_config = {
                    "url_column": st.selectbox(
                        "Select URL column",
                        options=mapping_data.columns.tolist(),
                        help="Column containing the page URLs"
                    ),
                    "id_column": st.selectbox(
                        "Select Form ID column",
                        options=mapping_data.columns.tolist(),
                        help="Column containing the form identifiers"
                    ),
                    "selected_columns": st.multiselect(
                        "Select additional columns to include",
                        options=[col for col in mapping_data.columns],
                        help="Choose which additional information to include in results"
                    )
                }

                # Analyse avec mapping
                analyzer = IframeAnalyzer()
                analyzed_df = analyzer.analyze_crm_data(
                    st.session_state.extraction_results,
                    mapping_data,
                    mapping_config
                )
                
                st.session_state.analyzed_df = analyzed_df

            except Exception as e:
                st.error(f"❌ Error loading file: {str(e)}")
                return
    
    # Affichage des résultats
    if st.session_state.analyzed_df is not None:
        st.dataframe(
            st.session_state.analyzed_df,
            use_container_width=True
        )

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