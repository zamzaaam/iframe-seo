import streamlit as st
import pandas as pd
from ..analysis import IframeAnalyzer
from io import StringIO, BytesIO
from typing import Dict, Optional
import logging
import re

# Initialisation du logger
logger = logging.getLogger('analysis_tab')

def sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Sanitize les données d'un DataFrame pour éviter les attaques XSS."""
    if df is None or df.empty:
        return df
    
    # Fonction pour sanitizer les chaînes individuelles
    def sanitize_value(val):
        if isinstance(val, str):
            # Remplacer les caractères potentiellement dangereux
            val = val.replace('<', '&lt;').replace('>', '&gt;')
            val = val.replace('"', '&quot;').replace("'", '&#39;')
            # Supprimer les scripts potentiels
            val = re.sub(r'javascript:', '', val, flags=re.IGNORECASE)
            val = re.sub(r'on\w+\s*=', '', val, flags=re.IGNORECASE)
        return val
    
    # Appliquer la sanitization à toutes les colonnes textuelles
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].apply(sanitize_value)
    
    return df

def validate_file_content(file) -> bool:
    """Valide le contenu d'un fichier téléchargé."""
    try:
        # Vérifier la taille du fichier
        file_content = file.read()
        file.seek(0)  # Remettre le curseur au début
        
        # Limiter la taille du fichier (10 MB)
        max_size = 10 * 1024 * 1024  # 10 MB
        if len(file_content) > max_size:
            st.error(f"File size exceeds the limit of 10 MB")
            return False
        
        # Vérifier le type MIME
        if file.type not in [
            'text/csv',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/octet-stream'
        ]:
            st.warning(f"Unexpected file type: {file.type}. Import may fail.")
        
        return True
    except Exception as e:
        logger.error(f"Error validating file content: {str(e)}")
        return False

def load_data_file(file):
    """Charge un fichier Excel ou CSV de façon sécurisée"""
    if not validate_file_content(file):
        return None
    
    try:
        # Chargement du fichier avec détection du séparateur
        if file.name.endswith('.csv'):
            # Essayer d'abord avec le séparateur point-virgule
            try:
                data = pd.read_csv(file, sep=';', encoding='utf-8')
            except:
                # Si ça échoue, essayer avec la virgule
                file.seek(0)  # Remettre le curseur au début du fichier
                data = pd.read_csv(file, sep=',', encoding='utf-8')
        else:
            # Pour les fichiers Excel, limiter les feuilles et colonnes
            data = pd.read_excel(file, engine='openpyxl', sheet_name=0)
        
        # Vérifier que le DataFrame n'est pas vide
        if data.empty:
            st.error("❌ The imported file appears to be empty")
            return None
                
        if len(data.columns) <= 1:
            st.error("❌ File format error: Could not properly detect columns. Please check the file separator")
            return None
        
        # Limiter le nombre de lignes (protection contre les fichiers trop grands)
        max_rows = 100000
        if len(data) > max_rows:
            st.warning(f"⚠️ File has more than {max_rows} rows. Only the first {max_rows} rows will be processed.")
            data = data.head(max_rows)
                
        # Sanitize les données
        data = sanitize_dataframe(data)
        
        st.success(f"✅ File loaded with {len(data)} rows and {len(data.columns)} columns")
        return data
        
    except Exception as e:
        st.error(f"❌ Error loading file: {str(e)}")
        logger.error(f"Error loading file: {str(e)}")
        return None

def display_summary(df):
    """Affiche un résumé des résultats"""
    st.subheader("📊 Summary", divider="blue")
    
    # Vérification de sécurité
    if df is None or df.empty:
        st.warning("No data available for analysis")
        return
    
    # Validation des colonnes requises
    required_columns = ['Form ID', 'CRM Campaign', 'URL source']
    for col in required_columns:
        if col not in df.columns:
            st.error(f"Required column '{col}' not found in data")
            return
    
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
    core_columns = ['URL source', 'Iframe', 'Form ID', 'CRM Campaign', 'Template', 'Cluster']
    url_columns = [col for col in df.columns if col not in core_columns and not col.startswith('CRM_')]
    crm_columns = [col for col in df.columns if col.startswith('CRM_')]
    
    # Afficher les colonnes du mapping URL
    if url_columns:
        st.subheader("📊 URL Mapping Metrics")
        metrics_cols = st.columns(min(4, len(url_columns)))
        
        for idx, col_name in enumerate(url_columns):
            with metrics_cols[idx % 4]:
                filled_values = df[col_name].notna().sum()
                st.metric(
                    f"{col_name}",
                    f"{filled_values}/{total_forms}",
                    help=f"Number of forms with {col_name} information"
                )
    
    # Afficher les colonnes du mapping CRM
    if crm_columns:
        st.subheader("📊 CRM Data Metrics")
        metrics_cols = st.columns(min(4, len(crm_columns)))
        
        for idx, col_name in enumerate(crm_columns):
            with metrics_cols[idx % 4]:
                filled_values = df[col_name].notna().sum()
                display_name = col_name.replace('CRM_', '')
                st.metric(
                    f"{display_name}",
                    f"{filled_values}/{total_forms}",
                    help=f"Number of forms with {display_name} information"
                )

    display_alerts(df)

def display_alerts(df):
    """Affiche les alertes sur les données"""
    if df is None or df.empty:
        return
        
    st.subheader("⚠️ Points of attention", divider="red")
    alerts = []
    
    # Vérifier uniquement les mauvaises intégrations
    try:
        bad_integration = df[df['Iframe'].str.contains("survey.dll", na=False)]
        if not bad_integration.empty:
            alerts.append({
                "severity": "error",
                "title": "Bad integrations",
                "message": f"{len(bad_integration)} forms with incorrect integration detected",
                "data": bad_integration[['URL source', 'Iframe', 'Form ID']]
            })
    except Exception as e:
        logger.error(f"Error checking bad integrations: {str(e)}")

    # Vérifier uniquement les URLs sans code CRM
    try:
        missing_crm = df[df['CRM Campaign'].isna()]
        if not missing_crm.empty:
            alerts.append({
                "severity": "warning",
                "title": "Missing CRM codes",
                "message": f"{len(missing_crm)} forms without CRM code",
                "data": missing_crm[['URL source', 'Form ID']]
            })
    except Exception as e:
        logger.error(f"Error checking missing CRM codes: {str(e)}")
    
    # Afficher les alertes
    if alerts:
        for idx, alert in enumerate(alerts):
            # Utiliser des boutons au lieu d'expanders pour éviter les problèmes d'imbrication
            if st.button(f"🔔 {alert['title']}", key=f"alert_{idx}"):
                if alert['severity'] == "error":
                    st.error(alert['message'])
                elif alert['severity'] == "warning":
                    st.warning(alert['message'])
                else:
                    st.info(alert['message'])
                    
                # Sanitize les données avant affichage
                alert_data = sanitize_dataframe(alert['data'])
                st.dataframe(
                    alert_data,
                    use_container_width=True,
                    column_config={"URL source": st.column_config.LinkColumn()}
                )
    else:
        st.success("✅ No anomalies detected")

def display_details(df):
    """Affiche les détails des données"""
    if df is None or df.empty:
        return
        
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
        crm_filter = "All"  # Valeur par défaut
        crm_campaign_filter = []
        
        crm_unique_values = df['CRM Campaign'].dropna().unique()
        if len(crm_unique_values) > 0:
            if len(crm_unique_values) <= 15:  # Limiter si trop de valeurs
                crm_campaign_filter = st.multiselect(
                    "Filter by CRM Campaign",
                    options=crm_unique_values
                )
            else:
                crm_filter = st.radio(
                    "CRM status",
                    ["All", "With CRM", "Without CRM"]
                )
    
    # Filtres pour les colonnes importées via URL mapping
    core_columns = ['URL source', 'Iframe', 'Form ID', 'CRM Campaign', 'Template', 'Cluster']
    url_columns = [col for col in df.columns if col not in core_columns and not col.startswith('CRM_')]
    
    url_filters = {}
    if url_columns:
        st.subheader("🔍 URL Mapping Filters")
        filter_columns = st.columns(min(3, len(url_columns)))
        
        for idx, col_name in enumerate(url_columns):
            with filter_columns[idx % 3]:
                # Obtenir les valeurs uniques en excluant les NaN
                unique_values = df[col_name].dropna().unique()
                if len(unique_values) > 0 and len(unique_values) <= 10:
                    url_filters[col_name] = st.multiselect(
                        f"Filter by {col_name}",
                        options=unique_values
                    )
    
    # Filtres pour les colonnes importées via données CRM
    crm_columns = [col for col in df.columns if col.startswith('CRM_')]
    
    crm_filters = {}
    if crm_columns:
        st.subheader("🔍 CRM Data Filters")
        filter_columns = st.columns(min(3, len(crm_columns)))
        
        for idx, col_name in enumerate(crm_columns):
            with filter_columns[idx % 3]:
                display_name = col_name.replace('CRM_', '')
                unique_values = df[col_name].dropna().unique()
                if len(unique_values) > 0 and len(unique_values) <= 10:
                    crm_filters[col_name] = st.multiselect(
                        f"Filter by {display_name}",
                        options=unique_values
                    )

    try:
        # Applique tous les filtres
        filtered_df = df.copy()
        
        # Filtre par Template
        if template_filter:
            filtered_df = filtered_df[filtered_df['Template'].isin(template_filter)]
        
        # Filtre par Cluster
        if cluster_filter:
            filtered_df = filtered_df[filtered_df['Cluster'].isin(cluster_filter)]
        
        # Filtre par CRM Campaign
        if crm_campaign_filter:
            filtered_df = filtered_df[filtered_df['CRM Campaign'].isin(crm_campaign_filter)]
        elif crm_filter != "All":
            if crm_filter == "With CRM":
                filtered_df = filtered_df[filtered_df['CRM Campaign'].notna()]
            elif crm_filter == "Without CRM":
                filtered_df = filtered_df[filtered_df['CRM Campaign'].isna()]
        
        # Filtres URL mapping
        for col_name, filter_values in url_filters.items():
            if filter_values:
                filtered_df = filtered_df[filtered_df[col_name].isin(filter_values)]
        
        # Filtres CRM
        for col_name, filter_values in crm_filters.items():
            if filter_values:
                filtered_df = filtered_df[filtered_df[col_name].isin(filter_values)]
        
        st.metric("Filtered results", len(filtered_df))
        
        # Préparer l'affichage en renommant les colonnes CRM pour plus de clarté
        display_df = filtered_df.copy()
        for col in display_df.columns:
            if col.startswith('CRM_'):
                display_df = display_df.rename(columns={col: col.replace('CRM_', '')})
        
        # Sanitize les données avant affichage
        display_df = sanitize_dataframe(display_df)
        
        st.dataframe(
            display_df,
            use_container_width=True,
            column_config={"URL source": st.column_config.LinkColumn()}
        )
    except Exception as e:
        st.error(f"Error filtering data: {str(e)}")
        logger.error(f"Error in display_details: {str(e)}")

def display_export(df):
    """Affiche les options d'export des résultats"""
    if df is None or df.empty:
        return
        
    st.subheader("💾 Export results")
    
    # Option pour renommer les colonnes CRM dans l'export
    rename_crm_cols = st.checkbox("Remove 'CRM_' prefix in column names for export", value=True)
    
    export_format = st.radio("Export format", ["CSV", "Excel"])
    col1, _ = st.columns([1, 3])
    
    with col1:
        try:
            # Préparer le DataFrame pour l'export
            export_df = df.copy()
            if rename_crm_cols:
                for col in export_df.columns:
                    if col.startswith('CRM_'):
                        export_df = export_df.rename(columns={col: col.replace('CRM_', '')})
            
            # Sanitize les données avant export
            export_df = sanitize_dataframe(export_df)
            
            if export_format == "CSV":
                output = StringIO()
                export_df.to_csv(output, index=False)
                st.download_button(
                    "📥 Download analysis (CSV)",
                    output.getvalue(),
                    "forms_analysis.csv",
                    "text/csv"
                )
            else:
                output = BytesIO()
                export_df.to_excel(output, engine='openpyxl', index=False)
                output.seek(0)
                st.download_button(
                    "📥 Download analysis (Excel)",
                    output.getvalue(),
                    "forms_analysis.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except Exception as e:
            st.error(f"Error generating export: {str(e)}")
            logger.error(f"Error in display_export: {str(e)}")

def display():
    """Affiche l'onglet analyse."""
    st.header("📊 Analysis", divider="rainbow")

    # Vérifie si des résultats sont disponibles
    if not st.session_state.extraction_results:
        st.info("ℹ️ Please extract data first in the Extraction tab.")
        return

    # Configuration du mapping
    with st.sidebar:
        st.subheader("🔄 Data Mapping")
        
        # Interface remaniée pour clarifier les différentes sources de données
        data_source = st.radio(
            "Select data source to import:",
            ["URL Mapping", "CRM Data", "Both"],
            help="Choose which type of data you want to import"
        )
        
        url_mapping_data = None
        crm_data = None
        url_mapping_config = None
        crm_mapping_config = None
        
        # Section pour l'import des données de mapping URL
        if data_source in ["URL Mapping", "Both"]:
            st.subheader("📄 URL Mapping Import")
            url_mapping_file = st.file_uploader(
                "Import URL mapping data (Excel/CSV)",
                type=['xlsx', 'csv'],
                help="Import a file containing URL-based mapping information",
                key="url_mapping_uploader"
            )

            if url_mapping_file:
                url_mapping_data = load_data_file(url_mapping_file)
                
                if url_mapping_data is not None:
                    # Aperçu des données - Sans utiliser d'expander
                    st.subheader("📊 Preview imported URL mapping")
                    
                    # Sanitize pour affichage
                    preview_df = sanitize_dataframe(url_mapping_data.head())
                    st.dataframe(preview_df)
                    
                    st.caption("Detected columns: " + ", ".join(url_mapping_data.columns.tolist()))

                    # Configuration des colonnes de mapping
                    url_mapping_config = {
                        "url_column": st.selectbox(
                            "Select URL column",
                            options=url_mapping_data.columns.tolist(),
                            help="Column containing the page URLs"
                        ),
                        "id_column": st.selectbox(
                            "Select Form ID column",
                            options=url_mapping_data.columns.tolist(),
                            help="Column containing the form identifiers"
                        ),
                        "selected_columns": st.multiselect(
                            "Select additional columns to include",
                            options=[col for col in url_mapping_data.columns],
                            help="Choose additional columns to include in the analysis"
                        )
                    }
        
        # Section pour l'import des données CRM
        if data_source in ["CRM Data", "Both"]:
            st.subheader("📄 CRM Data Import")
            crm_file = st.file_uploader(
                "Import CRM data (Excel/CSV)",
                type=['xlsx', 'csv'],
                help="Import a file containing CRM campaign information",
                key="crm_data_uploader"
            )

            if crm_file:
                crm_data = load_data_file(crm_file)
                
                if crm_data is not None:
                    # Aperçu des données - Sans utiliser d'expander
                    st.subheader("📊 Preview imported CRM data")
                    
                    # Sanitize pour affichage
                    preview_df = sanitize_dataframe(crm_data.head())
                    st.dataframe(preview_df)
                    
                    st.caption("Detected columns: " + ", ".join(crm_data.columns.tolist()))

                    # Configuration des colonnes CRM
                    crm_mapping_config = {
                        "crm_code_column": st.selectbox(
                            "Select CRM campaign code column",
                            options=crm_data.columns.tolist(),
                            help="Column containing the CRM campaign codes"
                        ),
                        "selected_columns": st.multiselect(
                            "Select CRM columns to include",
                            options=[col for col in crm_data.columns],
                            help="Choose which CRM data columns to include in the analysis"
                        )
                    }
        
        # Bouton pour lancer l'analyse
        if (url_mapping_data is not None or crm_data is not None):
            analyze_button = st.button("Analyze with imported data", type="primary")
            
            if analyze_button:
                try:
                    # Analyse avec les données importées
                    analyzer = IframeAnalyzer()
                    analyzed_df = analyzer.analyze_crm_data(
                        st.session_state.extraction_results,
                        url_mapping_data,
                        url_mapping_config,
                        crm_data,
                        crm_mapping_config
                    )
                    
                    # Sanitize le résultat
                    analyzed_df = sanitize_dataframe(analyzed_df)
                    
                    st.session_state.analyzed_df = analyzed_df
                    st.success("✅ Analysis completed successfully!")
                except Exception as e:
                    st.error(f"Error during analysis: {str(e)}")
                    logger.error(f"Analysis error: {str(e)}")
        
        # Option d'analyse sans données importées
        elif st.button("Analyze without imported data"):
            try:
                analyzer = IframeAnalyzer()
                analyzed_df = analyzer.analyze_crm_data(
                    st.session_state.extraction_results
                )
                
                # Sanitize le résultat
                analyzed_df = sanitize_dataframe(analyzed_df)
                
                st.session_state.analyzed_df = analyzed_df
                st.success("✅ Analysis completed with extraction data only")
            except Exception as e:
                st.error(f"Error during analysis: {str(e)}")
                logger.error(f"Analysis error: {str(e)}")
    
    # Affichage des résultats
    if st.session_state.analyzed_df is not None:
        # Affichage du résumé
        display_summary(st.session_state.analyzed_df)
        
        # Affichage des détails
        display_details(st.session_state.analyzed_df)
        
        # Options d'export
        display_export(st.session_state.analyzed_df)