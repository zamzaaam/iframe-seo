import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO, BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple
import time
import xml.etree.ElementTree as ET
import re
import json
import random  # Ajout de l'import random

# Configuration
MAX_WORKERS = 10
TIMEOUT = 5
CHUNK_SIZE = 50


def extract_id_and_code(url: str) -> Tuple[str, str]:
    """Extrait l'ID et le code CRM d'une URL iframe."""
    if not url:
        return None, None
    id_match = re.search(r'ID=([^&]+)', url)
    code_match = re.search(r'CODE=([^&]+)', url)
    return (id_match.group(1) if id_match else None,
            code_match.group(1) if code_match else None)


def create_session():
    """Crée une session avec des paramètres optimisés."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    return session


def extract_iframe_links(session: requests.Session, url: str) -> List[Dict]:
    """Extrait les liens iframe d'une URL donnée."""
    try:
        response = session.get(url, timeout=TIMEOUT)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        try:
            main_section = soup.find("body").find(
                "div").find("div").find("main")
            if not main_section:
                return []

            results = []
            for iframe in main_section.find_all("iframe"):
                src = iframe.get("src", "")
                if src.startswith("https://ovh.slgnt.eu/optiext/"):
                    form_id, crm_code = extract_id_and_code(src)
                    results.append({
                        "URL source": url,
                        "Iframe": src,
                        "Form ID": form_id,
                        "CRM Campaign": crm_code
                    })
            return results

        except AttributeError:
            return []

    except Exception as e:
        st.warning(f"Erreur pour {url}: {str(e)}")
        return []


def extract_urls_from_sitemap(sitemap_url: str) -> List[str]:
    """Extrait les URLs d'un sitemap."""
    try:
        session = create_session()
        response = session.get(sitemap_url, timeout=TIMEOUT)
        if response.status_code != 200:
            return []

        root = ET.fromstring(response.content)
        ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = [loc.text for loc in root.findall('.//ns:loc', ns)]
        return urls

    except Exception as e:
        st.warning(f"Erreur avec le sitemap {sitemap_url}: {str(e)}")
        return []


def process_urls_batch(urls: List[str], progress_bar) -> List[Dict]:
    """Traite un lot d'URLs en parallèle."""
    results = []
    session = create_session()
    completed_urls = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {
            executor.submit(extract_iframe_links, session, url): url
            for url in urls
        }

        for future in as_completed(future_to_url):
            url_results = future.result()
            if url_results:
                results.extend(url_results)
            completed_urls += 1
            progress_bar.progress(completed_urls / len(urls))

    return results


def load_template_mapping():
    """Charge le fichier JSON de mapping des templates depuis le dossier /data"""
    try:
        with open("data/template_mapping.json", "r") as f:
            template_mapping = json.load(f)
        return template_mapping
    except Exception as e:
        st.warning("⚠️ Impossible de charger le fichier de mapping des templates")
        return None


def get_template_name(form_id: str, template_mapping: dict) -> str:
    """Récupère le nom du template pour un ID donné"""
    if not form_id or not template_mapping:
        return None
    return template_mapping.get(form_id)


def analyze_crm_data(results: List[Dict], mapping_data: pd.DataFrame = None) -> pd.DataFrame:
    """Analyse les données CRM et applique le mapping si disponible."""
    df = pd.DataFrame(results)

    # Extraction des codes CRM des iframes
    df['CRM Campaign'] = df['Iframe'].apply(
        lambda x: extract_id_and_code(x)[1])

    if mapping_data is not None:
        # Fusion avec le mapping
        df = df.merge(
            mapping_data,
            left_on='Form ID',
            right_on='ID',
            how='left'
        )

        # Mise à jour des codes CRM manquants
        mask = df['CRM Campaign'].isna()
        if 'CRM_CAMPAIGN' in df.columns:
            df.loc[mask, 'CRM Campaign'] = df.loc[mask, 'CRM_CAMPAIGN']

        # Nettoyage des colonnes
        df = df.drop(['ID'], axis=1, errors='ignore')

    return df


def initialize_session_state():
    """Initialise les variables de session si elles n'existent pas."""
    if 'extraction_results' not in st.session_state:
        st.session_state.extraction_results = None
    if 'analyzed_results' not in st.session_state:
        st.session_state.analyzed_results = None
    if 'analyzed_df' not in st.session_state:
        st.session_state.analyzed_df = None
    if 'history' not in st.session_state:
        st.session_state.history = []


def save_to_history(results: List[Dict], input_urls: List[str], parameters: Dict, execution_time: float):
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


def display_extraction_tab():
    st.markdown("""
    This application extracts iframes from the path `//body/div/div/main/` 
    that start with `https://ovh.slgnt.eu/optiext/`.
    """)

    col1, col2 = st.columns([2, 1])

    with col1:
        input_type = st.radio(
            "Input type:",
            ["XML Sitemaps", "URLs List"]
        )

        if input_type == "XML Sitemaps":
            urls_input = st.text_area(
                "Sitemap URLs (one per line):",
                placeholder="https://example.com/sitemap.xml",
                height=200
            )
        else:
            urls_input = st.text_area(
                "URLs to analyze (one per line):",
                placeholder="https://example.com/page1",
                height=200
            )

    with col2:
        st.markdown("### Configuration")
        with st.expander("Advanced settings"):
            global MAX_WORKERS, TIMEOUT, CHUNK_SIZE

            # Mode test
            test_mode = st.checkbox("Enable test mode", False)
            test_urls = None
            if test_mode:
                test_urls = st.number_input(
                    "Number of URLs to test",
                    min_value=1,
                    max_value=1000,
                    value=10,
                    help="Limit the number of URLs to process for testing"
                )

            # Autres paramètres
            MAX_WORKERS = st.slider("Number of workers", 1, 20, 10)
            TIMEOUT = st.slider("Timeout (seconds)", 1, 15, 5)
            CHUNK_SIZE = st.slider("Batch size", 10, 100, 50)

    urls = [url.strip() for url in urls_input.splitlines() if url.strip()]

    # Bouton aligné à gauche
    col1, col2 = st.columns([1, 3])
    with col1:
        start_extraction = st.button("Extract iframes", type="primary")

    # La suite en pleine largeur
    if start_extraction:
        if not urls:
            st.warning("⚠️ Please enter at least one URL.")
            return

        with st.spinner("🔄 Processing..."):
            start_time = time.time()
            results = []
            processed_urls = []

            # Traitement des sitemaps
            if input_type == "XML Sitemaps":
                status_sitemap = st.empty()
                progress_sitemap = st.progress(0)

                for idx, sitemap_url in enumerate(urls):
                    status_sitemap.write(
                        f"📑 Reading sitemap: {sitemap_url}")
                    sitemap_urls = extract_urls_from_sitemap(sitemap_url)
                    processed_urls.extend(sitemap_urls)
                    progress_sitemap.progress((idx + 1) / len(urls))

                if processed_urls:
                    st.success(f"✅ {len(processed_urls)} URLs extracted from sitemaps")
                else:
                    st.error("❌ No URLs found in sitemaps")
                    return
            else:
                processed_urls = urls

            # Application du mode test si activé
            if test_mode and test_urls and len(processed_urls) > test_urls:
                st.info(f"🧪 Test mode enabled: randomly selecting {test_urls} URLs")
                processed_urls = random.sample(processed_urls, test_urls)

            # Traitement des URLs
            if processed_urls:
                status = st.empty()
                progress = st.progress(0)
                status.write(f"🔍 Analyzing {len(processed_urls)} URLs...")

                for i in range(0, len(processed_urls), CHUNK_SIZE):
                    chunk = processed_urls[i:i + CHUNK_SIZE]
                    status.write(f"🔍 Processing batch {i//CHUNK_SIZE + 1}/{len(processed_urls)//CHUNK_SIZE + 1}")
                    chunk_results = process_urls_batch(chunk, progress)
                    results.extend(chunk_results)

                if results:
                    execution_time = time.time() - start_time
                    st.session_state.extraction_results = results

                    # Sauvegarde dans l'historique
                    parameters = {
                        "test_mode": test_mode,
                        "test_urls": test_urls if test_mode else None,
                        "workers": MAX_WORKERS,
                        "timeout": TIMEOUT,
                        "chunk_size": CHUNK_SIZE
                    }
                    save_to_history(results, urls, parameters, execution_time)

                    st.success(f"""
                    ✨ Extraction completed in {execution_time:.2f} seconds!
                    - 📊 {len(processed_urls)} URLs analyzed
                    - 🎯 {len(results)} iframes found
                    """)

                    # Aperçu des résultats
                    st.markdown("### Results preview")
                    with st.expander("👀 View extracted data", expanded=True):
                        df = pd.DataFrame(results)
                        st.dataframe(
                            df[['URL source', 'Form ID', 'CRM Campaign']].head(10),
                            use_container_width=True
                        )
                        if len(results) > 10:
                            st.info(f"... and {len(results) - 10} more results")
                    
                    # Message pour rediriger vers l'analyse
                    st.info("💡 Go to the **Analysis** tab for a complete analysis!")

                else:
                    st.info("ℹ️ No iframes found.")


def display_analysis_tab():
    if not st.session_state.extraction_results:
        st.info("ℹ️ Please extract iframes first in the Extraction tab.")
        return

    st.header("🔍 Form Analysis", divider="rainbow")
    
    total_forms = len(st.session_state.extraction_results)
    st.caption(f"Last extraction: {total_forms} forms found")

    with st.sidebar:
        st.subheader("⚙️ Analysis Configuration")
        use_mapping = st.toggle("Use CRM mapping", value=False)
        
        mapping_data = None
        if use_mapping:
            mapping_file = st.file_uploader(
                "CRM mapping file (Excel)",
                type=['xlsx'],
                help="Expected format: columns 'ID' and 'CRM_CAMPAIGN'"
            )
            if mapping_file:
                try:
                    mapping_data = pd.read_excel(mapping_file)
                    st.success(f"✅ {len(mapping_data)} mappings loaded")
                except Exception as e:
                    st.error("❌ Format error")

    if st.session_state.analyzed_df is None:
        st.warning("⚠️ Click 'Start analysis' to begin")
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("📊 Start analysis", type="primary"):
                with st.spinner("Analyzing..."):
                    analyzed_df = analyze_crm_data(
                        st.session_state.extraction_results,
                        mapping_data
                    )
                    template_mapping = load_template_mapping()
                    
                    if template_mapping:
                        analyzed_df['Template'] = analyzed_df['Form ID'].apply(
                            lambda x: get_template_name(x, template_mapping)
                        )
                    st.session_state.analyzed_df = analyzed_df
                    st.rerun()
        return

    analyzed_df = st.session_state.analyzed_df

    summary_tab, details_tab, export_tab = st.tabs([
        "📈 Summary", "🔎 Details", "💾 Export"
    ])

    with summary_tab:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total forms", total_forms)

        with col2:
            st.markdown("#### Unique forms")
            total_unique = analyzed_df['Form ID'].nunique()
            templated = analyzed_df[analyzed_df['Template'].notna()]['Form ID'].nunique() if 'Template' in analyzed_df else 0
            not_templated = total_unique - templated
            
            st.metric("Total", total_unique)
            mc1, mc2 = st.columns(2)
            with mc1:
                st.metric("Templated", templated)
            with mc2:
                st.metric("Non-templated", not_templated)

        with col3:
            st.metric("With CRM code", analyzed_df['CRM Campaign'].notna().sum())
        with col4:
            st.metric("Without CRM code", analyzed_df['CRM Campaign'].isna().sum())

        st.subheader("⚠️ Points of attention", divider="red")
        alerts = []
        
        bad_integration = analyzed_df[analyzed_df['Iframe'].str.contains("survey.dll", na=False)]
        if not bad_integration.empty:
            alerts.append({
                "severity": "error",
                "title": "Bad integrations",
                "message": f"{len(bad_integration)} forms with incorrect integration detected",
                "data": bad_integration[['URL source', 'Iframe']]
            })

        missing_crm = analyzed_df[analyzed_df['CRM Campaign'].isna()]
        if not missing_crm.empty:
            alerts.append({
                "severity": "warning",
                "title": "Missing CRM codes",
                "message": f"{len(missing_crm)} forms without CRM code",
                "data": missing_crm[['URL source', 'Form ID']]
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
                        column_config={
                            "URL source": st.column_config.LinkColumn()
                        }
                    )
        else:
            st.success("✅ No anomalies detected")

    with details_tab:
        st.subheader("📑 Detailed data")
        
        col1, col2 = st.columns(2)
        with col1:
            template_filter = st.multiselect(
                "Filter by template",
                options=analyzed_df['Template'].unique() if 'Template' in analyzed_df.columns else []
            )
        with col2:
            crm_filter = st.radio(
                "CRM status",
                ["All", "With CRM", "Without CRM"]
            )

        filtered_df = analyzed_df.copy()
        if template_filter:
            filtered_df = filtered_df[filtered_df['Template'].isin(template_filter)]
        if crm_filter == "With CRM":
            filtered_df = filtered_df[filtered_df['CRM Campaign'].notna()]
        elif crm_filter == "Without CRM":
            filtered_df = filtered_df[filtered_df['CRM Campaign'].isna()]

        st.metric("Filtered results", len(filtered_df))
        st.dataframe(
            filtered_df,
            use_container_width=True,
            column_config={
                "URL source": st.column_config.LinkColumn()
            }
        )

    with export_tab:
        st.subheader("💾 Export results")
        
        export_format = st.radio(
            "Export format",
            ["CSV", "Excel"]
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            if export_format == "CSV":
                output = StringIO()
                analyzed_df.to_csv(output, index=False)
                st.download_button(
                    "📥 Download analysis (CSV)",
                    output.getvalue(),
                    "forms_analysis.csv",
                    "text/csv"
                )
            else:
                output = BytesIO()
                analyzed_df.to_excel(output, engine='openpyxl', index=False)
                output.seek(0)
                st.download_button(
                    "📥 Download analysis (Excel)",
                    output.getvalue(),
                    "forms_analysis.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    with st.sidebar:
        if st.button("🔄 Reset analysis"):
            st.session_state.analyzed_df = None
            st.rerun()


def display_history_tab():
    if not st.session_state.history:
        st.info("No extractions have been performed yet.")
    else:
        st.markdown("### Extraction history")

        history_data = []
        for idx, entry in enumerate(reversed(st.session_state.history)):
            history_data.append({
                "Date": entry["timestamp"],
                "Source URLs": entry["nb_input_urls"],
                "Iframes found": entry["nb_iframes_found"],
                "Duration (s)": f"{entry['execution_time']:.2f}",
                "Test mode": "✓" if entry["parameters"]["test_mode"] else "✗",
            })

        history_df = pd.DataFrame(history_data)
        st.dataframe(history_df, use_container_width=True)

        selected_idx = st.selectbox(
            "Select an extraction to view details",
            range(len(st.session_state.history)),
            format_func=lambda x: f"{st.session_state.history[-(x+1)]['timestamp']}"
        )

        if selected_idx is not None:
            entry = st.session_state.history[-(selected_idx+1)]

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
                if st.button("Reload this extraction", key=f"reload_{selected_idx}"):
                    st.session_state.extraction_results = entry["results"]
                    st.success(
                        "✨ Extraction reloaded! You can now analyze it in the 'Analysis' tab")

            with col1:
                output = StringIO()
                df = pd.DataFrame(entry["results"])
                df.to_csv(output, index=False)
                st.download_button(
                    "📥 Download results (CSV)",
                    output.getvalue(),
                    f"extraction_results_{entry['timestamp'].replace(' ', '_')}.csv",
                    "text/csv"
                )


def display_share_tab():
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
                 help="Copy the subject to clipboard",
                 on_click=lambda: st.write("Subject copied!"))
        st.button("📋 Copy message", key="copy_body",
                 help="Copy the message body to clipboard",
                 on_click=lambda: st.write("Message copied!"))


def main():
    st.set_page_config(
        page_title="iframe Form Extractor with CRM Analysis",
        page_icon="🔍",
        layout="wide"
    )

    st.title("iframe Forms Extractor and Analyzer")

    initialize_session_state()

    tabs = st.tabs(["Extraction", "Analysis", "History", "Share"])

    with tabs[0]:
        display_extraction_tab()

    with tabs[1]:
        display_analysis_tab()

    with tabs[2]:
        display_history_tab()

    with tabs[3]:
        display_share_tab()


if __name__ == "__main__":
    main()
