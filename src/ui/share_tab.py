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

    st.subheader("📝 Email template")
    
    subject = f"Forms Analysis Report - {time.strftime('%d/%m/%Y')}"
    body = generate_email_body(total_forms, unique_forms, templated, with_crm, without_crm, df)

    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Subject", value=subject)
        st.text_area("Message body", value=body, height=400)
        
    with col2:
        display_instructions()

def generate_email_body(total_forms, unique_forms, templated, with_crm, without_crm, df):
    body = f"""Hello,

Here are the results of the forms analysis:

SUMMARY:
• {total_forms} total forms analyzed
• {unique_forms} unique forms identified
  - including {templated} templated forms
  - including {unique_forms - templated} non-templated forms
• {with_crm} forms with CRM code
• {without_crm} forms without CRM code

ATTENTION POINTS:"""

    bad_integration = df[df['Iframe'].str.contains("survey.dll", na=False)]
    if not bad_integration.empty:
        body += f"\n• ⚠️ {len(bad_integration)} forms with incorrect integration"
    
    if without_crm > 0:
        body += f"\n• ⚠️ {without_crm} forms without CRM tracking"

    body += "\n\nBest regards"
    return body

def display_instructions():
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
