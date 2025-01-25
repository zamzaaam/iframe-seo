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
        use_mapping = st.toggle("Use CRM mapping", value=False)
        
        mapping_data = None
        if use_mapping:
            mapping_file = st.file_uploader(
                "CRM mapping file (Excel)",
                type=['xlsx']
            )
            if mapping_file:
                try:
                    mapping_data = pd.read_excel(mapping_file)
                    st.success(f"✅ {len(mapping_data)} mappings loaded")
                except Exception as e:
                    st.error("❌ Format error")

    if st.session_state.analyzed_df is None:
        st.warning("⚠️ Click 'Start analysis' to begin")
        col1, _ = st.columns([1, 3])
        with col1:
            if st.button("📊 Start analysis", type="primary"):
                with st.spinner("Analyzing..."):
                    analyzer = IframeAnalyzer()
                    analyzed_df = analyzer.analyze_crm_data(
                        st.session_state.extraction_results,
                        mapping_data
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
    templated = df[df['Template'].notna()]['Form ID'].nunique() if 'Template' in df else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total forms", total_forms)
    with col2:
        st.metric("Unique forms", total_unique)
    with col3:
        st.metric("With CRM code", df['CRM Campaign'].notna().sum())
    with col4:
        st.metric("Without CRM code", df['CRM Campaign'].isna().sum())

    display_alerts(df)

def display_details(df):
    st.subheader("📑 Detailed data")
    
    col1, col2 = st.columns(2)
    with col1:
        template_filter = st.multiselect(
            "Filter by template",
            options=df['Template'].unique() if 'Template' in df.columns else []
        )
    with col2:
        crm_filter = st.radio(
            "CRM status",
            ["All", "With CRM", "Without CRM"]
        )

    filtered_df = apply_filters(df, template_filter, crm_filter)
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
            "data": bad_integration[['URL source', 'CRM Campaign']]  # Changed columns
        })

    if not missing_crm.empty:
        alerts.append({
            "severity": "warning",
            "title": "Missing CRM codes",
            "message": f"{len(missing_crm)} forms without CRM code",
            "data": missing_crm[['URL source', 'CRM Campaign']]  # Changed columns
        })

    if alerts:
        for alert in alerts:
            with st.expander(f"🔔 {alert['title']}"):
                if alert['severity'] == "error":
                    st.error(alert['message'])
                else:
                    st.warning(alert['message'])
                st.dataframe(
                    alert['data'],
                    use_container_width=True,
                    column_config={"URL source": st.column_config.LinkColumn()}
                )
    else:
        st.success("✅ No anomalies detected")

def apply_filters(df, template_filter, crm_filter):
    filtered_df = df.copy()
    if template_filter:
        filtered_df = filtered_df[filtered_df['Template'].isin(template_filter)]
    if crm_filter == "With CRM":
        filtered_df = filtered_df[filtered_df['CRM Campaign'].notna()]
    elif crm_filter == "Without CRM":
        filtered_df = filtered_df[filtered_df['CRM Campaign'].isna()]
    return filtered_df
