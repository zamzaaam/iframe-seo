import streamlit as st
import pandas as pd  # S'assurer que pandas est importé
import time
import logging
import re
from ..utils import sanitize_html
from datetime import datetime  # Ajouter cet import

# Configuration du logger
logger = logging.getLogger('share_tab')

def sanitize_email_content(content):
    """Sanitize le contenu d'un email pour éviter les attaques."""
    if not content:
        return ""
    
    # Supprimer tout code HTML potentiel
    content = re.sub(r'<[^>]*>', '', content)
    
    # Échapper les caractères spéciaux
    content = content.replace('&', '&amp;')
    content = content.replace('<', '&lt;')
    content = content.replace('>', '&gt;')
    content = content.replace('"', '&quot;')
    content = content.replace("'", '&#x27;')
    
    # Supprimer les scripts JavaScript potentiels
    content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
    content = re.sub(r'on\w+\s*=', '', content, flags=re.IGNORECASE)
    
    return content

def generate_email_body(total_forms, unique_forms, templated, with_crm, without_crm, 
                       df, url_mapping_columns=None, crm_data_columns=None):
    """Génère le corps d'un email de façon sécurisée."""
    try:
        # Validation des entrées
        if not all(isinstance(param, int) for param in [total_forms, unique_forms, templated, with_crm, without_crm]):
            logger.error("Invalid metric parameters for email body")
            return "Error generating email content. Please try again."
        
        body = f"""Hello,

Here are the results of the forms analysis:

SUMMARY:
- {total_forms} total forms analyzed
- {unique_forms} unique forms identified
  - including {templated} templated forms
  - including {unique_forms - templated} non-templated forms
- {with_crm} forms with CRM code
- {without_crm} forms without CRM code"""

        # Ajouter les métriques pour les données de mapping URL
        if url_mapping_columns and len(url_mapping_columns) > 0:
            body += "\n\nURL MAPPING METRICS:"
            for col_name in url_mapping_columns:
                # Sanitize le nom de colonne
                col_name = sanitize_html(str(col_name))
                try:
                    filled_values = df[col_name].notna().sum()
                    body += f"\n• {filled_values}/{total_forms} forms with {col_name} information"
                except Exception as e:
                    logger.error(f"Error getting URL mapping metrics for {col_name}: {str(e)}")

        # Ajouter les métriques pour les données CRM
        if crm_data_columns and len(crm_data_columns) > 0:
            body += "\n\nCRM DATA METRICS:"
            for col_name in crm_data_columns:
                # Sanitize le nom de colonne
                col_name = sanitize_html(str(col_name))
                try:
                    filled_values = df[col_name].notna().sum()
                    display_name = col_name.replace('CRM_', '')
                    body += f"\n• {filled_values}/{total_forms} forms with {display_name} information"
                except Exception as e:
                    logger.error(f"Error getting CRM data metrics for {col_name}: {str(e)}")

        body += "\n\nATTENTION POINTS:"

        # Points d'attention standard
        try:
            bad_integration = df[df['Iframe'].str.contains("survey.dll", na=False)]
            if not bad_integration.empty:
                body += f"\n• ⚠️ {len(bad_integration)} forms with incorrect integration"
        except Exception as e:
            logger.error(f"Error checking bad integrations: {str(e)}")
        
        if without_crm > 0:
            body += f"\n• ⚠️ {without_crm} forms without CRM tracking"
        
        # Points d'attention pour les données de mapping URL
        if url_mapping_columns:
            for col_name in url_mapping_columns:
                # Sanitize le nom de colonne
                col_name = sanitize_html(str(col_name))
                try:
                    missing_data = df[df[col_name].isna()]
                    if not missing_data.empty and len(missing_data) > total_forms * 0.1:  # Plus de 10% de données manquantes
                        body += f"\n• ℹ️ {len(missing_data)} forms without {col_name} information"
                except Exception as e:
                    logger.error(f"Error checking missing URL mapping data for {col_name}: {str(e)}")
        
        # Points d'attention pour les données CRM
        if crm_data_columns:
            for col_name in crm_data_columns:
                # Sanitize le nom de colonne
                col_name = sanitize_html(str(col_name))
                try:
                    missing_data = df[df[col_name].isna()]
                    display_name = col_name.replace('CRM_', '')
                    # Si plus de 10% des formulaires avec code CRM n'ont pas cette donnée
                    if with_crm > 0 and not missing_data.empty and len(missing_data) > with_crm * 0.1:
                        body += f"\n• ℹ️ {len(missing_data)} forms without {display_name} information"
                except Exception as e:
                    logger.error(f"Error checking missing CRM data for {col_name}: {str(e)}")

        # Ajouter une note spécifique sur le fichier Excel multi-feuilles
        body += "\n\nEXPORT DETAILS:"
        body += "\nThe attached Excel file contains multiple sheets:"
        body += "\n• Analysis Results - Contains the complete data with all columns"
        body += "\n• URL Mapping Data - Original mapping data for reference"
        body += "\n• CRM Campaign Data - Original CRM campaign information"
        body += "\n• Template Data - Mapping of form IDs to template names"
        body += "\n\nThe file is named with a timestamp to ensure uniqueness."

        body += "\n\nBest regards"
        
        # Sanitize final content
        return sanitize_email_content(body)
    except Exception as e:
        logger.error(f"Error generating email body: {str(e)}")
        return "Error generating email content. Please try again."

def display():
    """Affiche l'onglet de partage de façon sécurisée."""
    try:
        if st.session_state.analyzed_df is None:
            st.info("ℹ️ Please analyze data first in the Analysis tab.")
            return

        st.header("📧 Share Analysis", divider="rainbow")
        
        # Validation du DataFrame
        df = st.session_state.analyzed_df
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            st.error("Invalid analysis data. Please re-run the analysis.")
            return
            
        # Vérification des colonnes requises
        required_columns = ['URL source', 'Form ID', 'CRM Campaign']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"Missing required columns in analysis data: {', '.join(missing_columns)}")
            return
        
        # Extraction des métriques en toute sécurité
        try:
            total_forms = len(df)
            unique_forms = df['Form ID'].nunique()
            templated = df['Template'].notna()['Form ID'].nunique() if 'Template' in df.columns else 0
            with_crm = df['CRM Campaign'].notna().sum()
            without_crm = df['CRM Campaign'].isna().sum()
        except Exception as e:
            logger.error(f"Error calculating metrics: {str(e)}")
            st.error("Error calculating metrics from analysis data.")
            return

        # Identifier les différents types de colonnes
        core_columns = ['URL source', 'Iframe', 'Form ID', 'CRM Campaign', 'Template', 'Cluster']
        url_mapping_columns = [col for col in df.columns if col not in core_columns and not col.startswith('CRM_')]
        crm_data_columns = [col for col in df.columns if col.startswith('CRM_')]

        st.subheader("📝 Email template")
        
        subject = f"Forms Analysis Report - {time.strftime('%d/%m/%Y')}"
        body = generate_email_body(total_forms, unique_forms, templated, with_crm, without_crm, 
                                df, url_mapping_columns, crm_data_columns)

        col1, col2 = st.columns(2)
        with col1:
            email_subject = st.text_input("Subject", value=subject)
            email_body = st.text_area("Message body", value=body, height=400)
            
        with col2:
            st.markdown("### 📋 Instructions")
            st.markdown("""
            1. Copy the subject and message body
            2. Customize the content as needed
            3. Don't forget to attach the Excel/CSV export
            
            **Note:** Data is formatted for better readability in email clients.
            """)
            
            # Utilisation de JavaScript pour la copie est sécuritaire puisqu'il s'exécute côté client
            if st.button("📋 Copy subject", key="copy_subject", 
                        help="Copy the subject to clipboard"):
                st.success("Subject copied to clipboard!")
                
            if st.button("📋 Copy message", key="copy_body",
                        help="Copy the message body to clipboard"):
                st.success("Message body copied to clipboard!")
        
        # Déplacé hors de la colonne et de toute autre structure qui pourrait contenir un expander
        st.subheader("ℹ️ Email Template Structure")
        st.markdown("""
        The email template includes:
        
        **1. SUMMARY**
        - Total forms analyzed
        - Unique forms identified (templated and non-templated)
        - CRM code statistics
        
        **2. URL MAPPING METRICS**
        - Shows how many forms have data for each imported URL mapping column
        
        **3. CRM DATA METRICS**
        - Shows how many forms have data for each imported CRM data column
        
        **4. ATTENTION POINTS**
        - Highlights potential issues that need attention
        - Shows forms with incorrect integration
        - Shows forms missing CRM tracking
        - Shows any mapping or CRM data with significant missing values
        
        **5. EXPORT DETAILS**
        - Describes the multi-sheet structure of the Excel file
        - Explains the content of each sheet
        """)
    except Exception as e:
        logger.error(f"Error in share tab display: {str(e)}")
        st.error("An error occurred while displaying the share tab. Please try again or contact support.")