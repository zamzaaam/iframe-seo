import streamlit as st
import pandas as pd
from ..analysis import IframeAnalyzer
from io import StringIO, BytesIO
from typing import Dict

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

                # Configuration minimale des colonnes de mapping
                # On ne demande plus à l'utilisateur de sélectionner les colonnes supplémentaires
                # La détection sera automatique pour CRM Campaign Code et Cluster
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
                    # On garde cette option mais elle devient facultative
                    "selected_columns": st.multiselect(
                        "Select additional columns to include (optional)",
                        options=[col for col in mapping_data.columns],
                        help="Choose additional columns to include beyond CRM Campaign Code and Cluster"
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
        # Affichage du résumé
        display_summary(st.session_state.analyzed_df)
        
        # Affichage des détails
        display_details(st.session_state.analyzed_df)
        
        # Options d'export
        display_export(st.session_state.analyzed_df)

def display_summary(df):
    """Affiche un résumé des résultats"""
    st.subheader("📊 Summary", divider="blue")
    
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

    # Afficher les métriques pour les colonnes importées (excepté Cluster)
    imported_columns = [col for col in df.columns if col not in ['URL source', 'Iframe', 'Form ID', 'CRM Campaign', 'Template', 'Cluster']]
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
    
    st.subheader("🔍 Filters")
    
    # Filtres fusionnés dans une interface unifiée
    col1, col2, col3 = st.columns(3)
    
    with col1:
        template_filter = st.multiselect(
            "Filter by Template",
            options=df['Template'].dropna().unique() if 'Template' in df.columns else []
        )
    
    with col2:
        # Filtre pour Cluster s'il existe
        cluster_filter = []
        if 'Cluster' in df.columns:
            unique_clusters = df['Cluster'].dropna().unique()
            if len(unique_clusters) > 0:
                cluster_filter = st.multiselect(
                    "Filter by Cluster",
                    options=unique_clusters
                )
    
    with col3:
        # Filtre pour CRM Campaign
        crm_unique_values = df['CRM Campaign'].dropna().unique()
        if len(crm_unique_values) > 0 and len(crm_unique_values) <= 15:  # Limiter si trop de valeurs
            crm_campaign_filter = st.multiselect(
                "Filter by CRM Campaign",
                options=crm_unique_values
            )
        else:
            crm_campaign_filter = []
            crm_filter = st.radio(
                "CRM status",
                ["All", "With CRM", "Without CRM"]
            )
    
    # Filtres pour les autres colonnes importées (excluant Cluster qui est déjà filtré)
    other_columns = [col for col in df.columns if col not in ['URL source', 'Iframe', 'Form ID', 'CRM Campaign', 'Template', 'Cluster']]
    other_filters = {}
    
    if other_columns:
        st.subheader("🔍 Additional filters")
        filter_columns = st.columns(min(3, len(other_columns)))
        
        for idx, col_name in enumerate(other_columns):
            with filter_columns[idx % 3]:
                # Obtenir les valeurs uniques en excluant les NaN
                unique_values = df[col_name].dropna().unique()
                if len(unique_values) > 0 and len(unique_values) <= 10:  # Seulement pour les colonnes avec un nombre raisonnable de valeurs uniques
                    other_filters[col_name] = st.multiselect(
                        f"Filter by {col_name}",
                        options=unique_values
                    )

    # Applique tous les filtres
    filtered_df = df.copy()
    
    # Filtre par Template
    if template_filter:
        filtered_df = filtered_df[filtered_df['Template'].isin(template_filter)]
    
    # Filtre par Cluster
    if cluster_filter:
        filtered_df = filtered_df[filtered_df['Cluster'].isin(cluster_filter)]
    
    # Filtre par CRM Campaign
    if 'crm_campaign_filter' in locals() and crm_campaign_filter:
        filtered_df = filtered_df[filtered_df['CRM Campaign'].isin(crm_campaign_filter)]
    elif 'crm_filter' in locals():
        if crm_filter == "With CRM":
            filtered_df = filtered_df[filtered_df['CRM Campaign'].notna()]
        elif crm_filter == "Without CRM":
            filtered_df = filtered_df[filtered_df['CRM Campaign'].isna()]
    
    # Autres filtres
    for col_name, filter_values in other_filters.items():
        if filter_values:
            filtered_df = filtered_df[filtered_df[col_name].isin(filter_values)]
    
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
            "data": bad_integration[['URL source', 'Iframe', 'Form ID']]
        })

    if not missing_crm.empty:
        alerts.append({
            "severity": "warning",
            "title": "Missing CRM codes",
            "message": f"{len(missing_crm)} forms without CRM code",
            "data": missing_crm[['URL source', 'Form ID']]
        })
    
    # Alertes pour les colonnes importées sauf "Cluster"
    imported_columns = [col for col in df.columns if col not in ['URL source', 'Iframe', 'Form ID', 'CRM Campaign', 'Template', 'Cluster']]
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