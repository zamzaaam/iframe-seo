import streamlit as st
import time

def display():
    if st.session_state.analyzed_df is None:
        st.info("ℹ️ Please analyze data first in the Analysis tab.")
        return

    st.header("📧 Share Analysis", divider="rainbow")
    
    df = st.session_state.analyzed_df
    total_forms = len(df)
    unique_forms = df['Form ID'].nunique()
    templated = df[df['Template'].notna()]['Form ID'].nunique() if 'Template' in df.columns else 0
    with_crm = df['CRM Campaign'].notna().sum()
    without_crm = df['CRM Campaign'].isna().sum()

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
        st.text_input("Subject", value=subject)
        st.text_area("Message body", value=body, height=400)
        
    with col2:
        st.markdown("### 📋 Instructions")
        st.markdown("""
        1. Copy the subject and message body
        2. Customize the content as needed
        3. Don't forget to attach the Excel/CSV export
        
        **Note:** Data is formatted for better readability in email clients.
        """)
        
        st.button("📋 Copy subject", key="copy_subject", 
                help="Copy the subject to clipboard")
        st.button("📋 Copy message", key="copy_body",
                help="Copy the message body to clipboard")
    
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
    """)

def generate_email_body(total_forms, unique_forms, templated, with_crm, without_crm, 
                       df, url_mapping_columns=None, crm_data_columns=None):
    body = f"""Hello,

Here are the results of the forms analysis:

SUMMARY:
• {total_forms} total forms analyzed
• {unique_forms} unique forms identified
  - including {templated} templated forms
  - including {unique_forms - templated} non-templated forms
• {with_crm} forms with CRM code
• {without_crm} forms without CRM code"""

    # Ajouter les métriques pour les données de mapping URL
    if url_mapping_columns and len(url_mapping_columns) > 0:
        body += "\n\nURL MAPPING METRICS:"
        for col_name in url_mapping_columns:
            filled_values = df[col_name].notna().sum()
            body += f"\n• {filled_values}/{total_forms} forms with {col_name} information"

    # Ajouter les métriques pour les données CRM
    if crm_data_columns and len(crm_data_columns) > 0:
        body += "\n\nCRM DATA METRICS:"
        for col_name in crm_data_columns:
            filled_values = df[col_name].notna().sum()
            display_name = col_name.replace('CRM_', '')
            body += f"\n• {filled_values}/{total_forms} forms with {display_name} information"

    body += "\n\nATTENTION POINTS:"

    # Points d'attention standard
    bad_integration = df[df['Iframe'].str.contains("survey.dll", na=False)]
    if not bad_integration.empty:
        body += f"\n• ⚠️ {len(bad_integration)} forms with incorrect integration"
    
    if without_crm > 0:
        body += f"\n• ⚠️ {without_crm} forms without CRM tracking"
    
    # Points d'attention pour les données de mapping URL
    if url_mapping_columns:
        for col_name in url_mapping_columns:
            missing_data = df[df[col_name].isna()]
            if not missing_data.empty and len(missing_data) > total_forms * 0.1:  # Plus de 10% de données manquantes
                body += f"\n• ℹ️ {len(missing_data)} forms without {col_name} information"
    
    # Points d'attention pour les données CRM
    if crm_data_columns:
        for col_name in crm_data_columns:
            missing_data = df[df[col_name].isna()]
            display_name = col_name.replace('CRM_', '')
            # Si plus de 10% des formulaires avec code CRM n'ont pas cette donnée
            if with_crm > 0 and not missing_data.empty and len(missing_data) > with_crm * 0.1:
                body += f"\n• ℹ️ {len(missing_data)} forms without {display_name} information"

    body += "\n\nBest regards"
    return body