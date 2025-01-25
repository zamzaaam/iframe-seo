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
    """Affiche et gère l'onglet d'extraction"""
    st.markdown("""
    Cette application extrait les iframes du chemin `//body/div/div/main/` 
    qui commencent par `https://ovh.slgnt.eu/optiext/`.
    """)

    col1, col2 = st.columns([2, 1])

    with col1:
        input_type = st.radio(
            "Type d'entrée :",
            ["Sitemaps XML", "Liste d'URLs"]
        )

        if input_type == "Sitemaps XML":
            urls_input = st.text_area(
                "URLs des sitemaps (une par ligne) :",
                placeholder="https://example.com/sitemap.xml",
                height=200
            )
        else:
            urls_input = st.text_area(
                "URLs à analyser (une par ligne) :",
                placeholder="https://example.com/page1",
                height=200
            )

    with col2:
        st.markdown("### Configuration")
        with st.expander("Paramètres avancés"):
            global MAX_WORKERS, TIMEOUT, CHUNK_SIZE

            # Mode test
            test_mode = st.checkbox("Activer le mode test", False)
            test_urls = None
            if test_mode:
                test_urls = st.number_input(
                    "Nombre d'URLs à tester",
                    min_value=1,
                    max_value=1000,
                    value=10,
                    help="Limite le nombre d'URLs à traiter pour les tests"
                )

            # Autres paramètres
            MAX_WORKERS = st.slider("Nombre de workers", 1, 20, 10)
            TIMEOUT = st.slider("Timeout (secondes)", 1, 15, 5)
            CHUNK_SIZE = st.slider("Taille des lots", 10, 100, 50)

    urls = [url.strip() for url in urls_input.splitlines() if url.strip()]

    # Bouton aligné à gauche
    col1, col2 = st.columns([1, 3])
    with col1:
        start_extraction = st.button("Extraire les iframes", type="primary")

    # La suite en pleine largeur
    if start_extraction:
        if not urls:
            st.warning("⚠️ Veuillez entrer au moins une URL.")
            return

        with st.spinner("🔄 Traitement en cours..."):
            start_time = time.time()
            results = []
            processed_urls = []

            # Traitement des sitemaps
            if input_type == "Sitemaps XML":
                status_sitemap = st.empty()
                progress_sitemap = st.progress(0)

                for idx, sitemap_url in enumerate(urls):
                    status_sitemap.write(
                        f"📑 Lecture du sitemap: {sitemap_url}")
                    sitemap_urls = extract_urls_from_sitemap(sitemap_url)
                    processed_urls.extend(sitemap_urls)
                    progress_sitemap.progress((idx + 1) / len(urls))

                if processed_urls:
                    st.success(f"✅ {len(processed_urls)
                                    } URLs extraites des sitemaps")
                else:
                    st.error("❌ Aucune URL trouvée dans les sitemaps")
                    return
            else:
                processed_urls = urls

            # Application du mode test si activé
            if test_mode and test_urls and len(processed_urls) > test_urls:
                st.info(f"🧪 Mode test activé : sélection aléatoire de {test_urls} URLs")
                processed_urls = random.sample(processed_urls, test_urls)

            # Traitement des URLs
            if processed_urls:
                status = st.empty()
                progress = st.progress(0)
                status.write(f"🔍 Analyse de {len(processed_urls)} URLs...")

                for i in range(0, len(processed_urls), CHUNK_SIZE):
                    chunk = processed_urls[i:i + CHUNK_SIZE]
                    status.write(f"🔍 Traitement du lot {
                                 i//CHUNK_SIZE + 1}/{len(processed_urls)//CHUNK_SIZE + 1}")
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
                    ✨ Extraction terminée en {execution_time:.2f} secondes !
                    - 📊 {len(processed_urls)} URLs analysées
                    - 🎯 {len(results)} iframes trouvés
                    """)

                    # Aperçu des résultats
                    st.markdown("### Aperçu des résultats")
                    with st.expander("👀 Voir les données extraites", expanded=True):
                        df = pd.DataFrame(results)
                        st.dataframe(
                            df[['URL source', 'Form ID', 'CRM Campaign']].head(10),
                            use_container_width=True
                        )
                        if len(results) > 10:
                            st.info(f"... et {len(results) - 10} autres résultats")
                    
                    # Message pour rediriger vers l'analyse
                    st.info("💡 Rendez-vous dans l'onglet **Analyse** pour une analyse complète de l'extraction !")

                else:
                    st.info("ℹ️ Aucun iframe trouvé.")


def display_analysis_tab():
    """Affiche l'onglet d'analyse avec une meilleure expérience utilisateur"""
    if not st.session_state.extraction_results:
        st.info("ℹ️ Veuillez d'abord extraire des iframes dans l'onglet Extraction.")
        return

    # En-tête avec stats rapides
    st.header("🔍 Analyse des formulaires", divider="rainbow")
    
    total_forms = len(st.session_state.extraction_results)
    st.caption(f"Dernière extraction : {total_forms} formulaires trouvés")

    # Configuration dans une sidebar pour plus d'espace
    with st.sidebar:
        st.subheader("⚙️ Configuration de l'analyse")
        use_mapping = st.toggle("Utiliser un mapping CRM", value=False)
        
        mapping_data = None
        if use_mapping:
            mapping_file = st.file_uploader(
                "Fichier de mapping CRM (Excel)",
                type=['xlsx'],
                help="Format attendu : colonnes 'ID' et 'CRM_CAMPAIGN'"
            )
            if mapping_file:
                try:
                    mapping_data = pd.read_excel(mapping_file)
                    st.success(f"✅ {len(mapping_data)} mappings chargés")
                except Exception as e:
                    st.error("❌ Erreur de format")

    # Analyse des données si pas encore fait
    if st.session_state.analyzed_df is None:
        st.warning("⚠️ Cliquez sur 'Lancer l'analyse' pour commencer")
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("📊 Lancer l'analyse", type="primary"):
                with st.spinner("Analyse en cours..."):
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
                    st.rerun()  # Changed from st.experimental_rerun()
        return

    # Récupération des données analysées
    analyzed_df = st.session_state.analyzed_df

    # Création de 3 onglets pour une meilleure organisation
    summary_tab, details_tab, export_tab = st.tabs([
        "📈 Synthèse", "🔎 Détails", "💾 Export"
    ])

    with summary_tab:
        # Métriques principales en colonnes
        col1, col2, col3, col4 = st.columns(4)  # Retour à 4 colonnes
        with col1:
            st.metric("Total formulaires", total_forms)

        # Remplacer la métrique simple par un conteneur détaillé
        with col2:
            st.markdown("#### Formulaires uniques")
            total_unique = analyzed_df['Form ID'].nunique()
            templated = analyzed_df[analyzed_df['Template'].notna()]['Form ID'].nunique() if 'Template' in analyzed_df else 0
            not_templated = total_unique - templated
            
            st.metric("Total", total_unique)
            mc1, mc2 = st.columns(2)
            with mc1:
                st.metric("Templatisés", templated)
            with mc2:
                st.metric("Non templatisés", not_templated)

        with col3:
            st.metric("Avec code CRM", analyzed_df['CRM Campaign'].notna().sum())
        with col4:
            st.metric("Sans code CRM", analyzed_df['CRM Campaign'].isna().sum())

        # Section alertes (suppression de la visualisation des templates)
        st.subheader("⚠️ Points d'attention", divider="red")
        alerts = []
        
        # Mauvaises intégrations
        bad_integration = analyzed_df[analyzed_df['Iframe'].str.contains("survey.dll", na=False)]
        if not bad_integration.empty:
            alerts.append({
                "severity": "error",
                "title": "Mauvaises intégrations",
                "message": f"{len(bad_integration)} formulaires mal intégrés détectés",
                "data": bad_integration[['URL source', 'Iframe']]
            })

        # CRM manquants
        missing_crm = analyzed_df[analyzed_df['CRM Campaign'].isna()]
        if not missing_crm.empty:
            alerts.append({
                "severity": "warning",
                "title": "Codes CRM manquants",
                "message": f"{len(missing_crm)} formulaires sans code CRM",
                "data": missing_crm[['URL source', 'Form ID']]
            })

        # Affichage des alertes
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
            st.success("✅ Aucune anomalie détectée")

    with details_tab:
        st.subheader("📑 Données détaillées")
        
        # Filtres
        col1, col2 = st.columns(2)
        with col1:
            template_filter = st.multiselect(
                "Filtrer par template",
                options=analyzed_df['Template'].unique() if 'Template' in analyzed_df.columns else []
            )
        with col2:
            crm_filter = st.radio(
                "Statut CRM",
                ["Tous", "Avec CRM", "Sans CRM"]
            )

        # Application des filtres
        filtered_df = analyzed_df.copy()
        if template_filter:
            filtered_df = filtered_df[filtered_df['Template'].isin(template_filter)]
        if crm_filter == "Avec CRM":
            filtered_df = filtered_df[filtered_df['CRM Campaign'].notna()]
        elif crm_filter == "Sans CRM":
            filtered_df = filtered_df[filtered_df['CRM Campaign'].isna()]

        # Affichage données filtrées avec métrique
        st.metric("Résultats filtrés", len(filtered_df))
        st.dataframe(
            filtered_df,
            use_container_width=True,
            column_config={
                "URL source": st.column_config.LinkColumn()
            }
        )

    with export_tab:
        st.subheader("💾 Exporter les résultats")
        
        export_format = st.radio(
            "Format d'export",
            ["CSV", "Excel"]
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            if export_format == "CSV":
                output = StringIO()
                analyzed_df.to_csv(output, index=False)
                st.download_button(
                    "📥 Télécharger l'analyse (CSV)",
                    output.getvalue(),
                    "analyse_formulaires.csv",
                    "text/csv"
                )
            else:
                output = BytesIO()
                analyzed_df.to_excel(output, engine='openpyxl', index=False)
                output.seek(0)
                st.download_button(
                    "📥 Télécharger l'analyse (Excel)",
                    output.getvalue(),
                    "analyse_formulaires.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    # Bouton pour réinitialiser l'analyse déplacé en haut de la sidebar
    with st.sidebar:
        if st.button("🔄 Réinitialiser l'analyse"):
            st.session_state.analyzed_df = None
            st.rerun()  # Changed from st.experimental_rerun()


def display_history_tab():
    """Affiche l'onglet historique"""
    if not st.session_state.history:
        st.info("Aucune extraction n'a encore été effectuée.")
    else:
        st.markdown("### Historique des extractions")

        # Affichage du tableau récapitulatif
        history_data = []
        for idx, entry in enumerate(reversed(st.session_state.history)):
            history_data.append({
                "Date": entry["timestamp"],
                "URLs sources": entry["nb_input_urls"],
                "Iframes trouvés": entry["nb_iframes_found"],
                "Durée (s)": f"{entry['execution_time']:.2f}",
                "Mode test": "✓" if entry["parameters"]["test_mode"] else "✗",
            })

        history_df = pd.DataFrame(history_data)
        st.dataframe(history_df, use_container_width=True)

        # Sélection d'une extraction pour plus de détails
        selected_idx = st.selectbox(
            "Sélectionner une extraction pour voir les détails",
            range(len(st.session_state.history)),
            format_func=lambda x: f"{
                st.session_state.history[-(x+1)]['timestamp']}"
        )

        if selected_idx is not None:
            entry = st.session_state.history[-(selected_idx+1)]

            # Affichage des détails
            st.markdown("### Détails de l'extraction")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("URLs analysées", entry["nb_input_urls"])
            with col2:
                st.metric("Iframes trouvés", entry["nb_iframes_found"])
            with col3:
                st.metric("Durée", f"{entry['execution_time']:.2f}s")

            # Paramètres utilisés
            st.markdown("#### Paramètres")
            params = entry["parameters"]
            st.json(params)

            # URLs sources
            st.markdown("#### URLs sources")
            st.write(entry["input_urls"])

            # Actions sur l'extraction
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("Recharger cette extraction", key=f"reload_{selected_idx}"):
                    st.session_state.extraction_results = entry["results"]
                    st.success(
                        "✨ Extraction rechargée! Vous pouvez maintenant l'analyser dans l'onglet 'Analyse'")

            with col1:
                # Export des résultats
                output = StringIO()
                df = pd.DataFrame(entry["results"])
                df.to_csv(output, index=False)
                st.download_button(
                    "📥 Télécharger les résultats (CSV)",
                    output.getvalue(),
                    f"resultats_extraction_{
                        entry['timestamp'].replace(' ', '_')}.csv",
                    "text/csv"
                )


def display_share_tab():
    """Affiche l'onglet de partage avec modèle d'email"""
    if st.session_state.analyzed_df is None:  # Changed from "if not st.session_state.analyzed_df:"
        st.info("ℹ️ Veuillez d'abord analyser des données dans l'onglet Analyse.")
        return

    st.header("📧 Partager l'analyse", divider="rainbow")
    
    # Récupération des métriques clés
    df = st.session_state.analyzed_df
    total_forms = len(df)
    unique_forms = df['Form ID'].nunique()
    templated = df[df['Template'].notna()]['Form ID'].nunique() if 'Template' in df.columns else 0
    with_crm = df['CRM Campaign'].notna().sum()
    without_crm = df['CRM Campaign'].isna().sum()

    # Génération du modèle d'email
    st.subheader("📝 Modèle d'email")
    
    subject = f"Rapport d'analyse des formulaires - {time.strftime('%d/%m/%Y')}"
    body = f"""Bonjour,

Je vous partage les résultats de l'analyse des formulaires :

SYNTHÈSE :
• {total_forms} formulaires analysés au total
• {unique_forms} formulaires uniques identifiés
  - dont {templated} formulaires templatisés
  - dont {unique_forms - templated} formulaires non templatisés
• {with_crm} formulaires avec code CRM
• {without_crm} formulaires sans code CRM

POINTS D'ATTENTION :"""

    # Ajout des alertes si présentes
    bad_integration = df[df['Iframe'].str.contains("survey.dll", na=False)]
    if not bad_integration.empty:
        body += f"\n• ⚠️ {len(bad_integration)} formulaires mal intégrés détectés"
    
    if without_crm > 0:
        body += f"\n• ⚠️ {without_crm} formulaires sans remontée CRM"

    body += "\n\nCordialement"

    # Affichage et copie
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Objet", value=subject)
        st.text_area("Corps du message", value=body, height=400)
        
    with col2:
        st.markdown("### 📋 Instructions")
        st.markdown("""
        1. Copiez l'objet et le corps du message
        2. Personnalisez le contenu selon vos besoins
        3. N'oubliez pas de joindre l'export Excel/CSV de l'analyse
        
        **Note :** Les données sont formatées pour une meilleure lisibilité dans un client email.
        """)
        
        # Boutons de copie rapide
        st.button("📋 Copier l'objet", key="copy_subject", 
                 help="Copie l'objet dans le presse-papier",
                 on_click=lambda: st.write("Objet copié !"))
        st.button("📋 Copier le message", key="copy_body",
                 help="Copie le corps du message dans le presse-papier",
                 on_click=lambda: st.write("Message copié !"))


def main():
    st.set_page_config(
        page_title="Extracteur d'iframes avec analyse CRM",
        page_icon="🔍",
        layout="wide"
    )

    st.title("Extraction et analyse des iframes")

    # Initialisation des variables de session
    initialize_session_state()

    # Interface principale
    tabs = st.tabs(["Extraction", "Analyse", "Historique", "Partager"])  # Ajout du nouvel onglet

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
