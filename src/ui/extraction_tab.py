import streamlit as st
from ..config import Config
from ..extractors import SitemapExtractor, IframeExtractor, SitemapDiscoveryExtractor
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_urls_batch(urls, progress_bar):
    results = []
    extractor = IframeExtractor()
    completed_urls = 0

    with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
        future_to_url = {
            executor.submit(extractor.extract_from_url, url): url
            for url in urls
        }

        for future in as_completed(future_to_url):
            url_results = future.result()
            if url_results:
                results.extend(url_results)
            completed_urls += 1
            progress_bar.progress(completed_urls / len(urls))

    return results

def initialize_sitemap_discovery():
    """Initialise l'état de session pour la découverte de sitemaps."""
    if 'discovered_sitemaps' not in st.session_state:
        st.session_state.discovered_sitemaps = []
    if 'selected_sitemaps' not in st.session_state:
        st.session_state.selected_sitemaps = []

def display_sitemap_discovery():
    """Affiche l'interface de découverte de sitemaps."""
    st.subheader("🧭 Sitemap Discovery")
    
    # Champ de saisie pour l'URL de base
    base_url = st.text_input(
        "Enter website URL:",
        placeholder="https://example.com",
    )
    
    col1, _ = st.columns([1, 3])
    with col1:
        discover_button = st.button("🔍 Discover Sitemaps", type="primary")
    
    if discover_button and base_url:
        with st.spinner("🔄 Discovering sitemaps..."):
            # Effectuer la découverte
            discovery_extractor = SitemapDiscoveryExtractor()
            discovered = discovery_extractor.discover_sitemaps(base_url)
            
            if discovered:
                st.session_state.discovered_sitemaps = discovered
                # Par défaut, tout sélectionner
                st.session_state.selected_sitemaps = [s["url"] for s in discovered]
                st.success(f"✅ Found {len(discovered)} sitemaps!")
            else:
                st.warning("⚠️ No sitemaps found. Try entering a different URL.")
    
    # Afficher les sitemaps découverts s'ils existent
    if st.session_state.discovered_sitemaps:
        st.subheader("📑 Discovered Sitemaps")
        
        # Options de sélection
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Select All"):
                st.session_state.selected_sitemaps = [s["url"] for s in st.session_state.discovered_sitemaps]
                st.rerun()
        with col2:
            if st.button("Deselect All"):
                st.session_state.selected_sitemaps = []
                st.rerun()
        
        # Affichage des sitemaps avec cases à cocher
        st.markdown("### Select sitemaps to extract URLs from:")
        
        for i, sitemap in enumerate(st.session_state.discovered_sitemaps):
            # Indentation pour montrer la hiérarchie
            prefix = "   " * sitemap["depth"]
            icon = "📚 " if sitemap["is_index"] else "📄 "
            
            # Cases à cocher
            is_selected = sitemap["url"] in st.session_state.selected_sitemaps
            if st.checkbox(
                f"{prefix}{icon} {sitemap['url']}",
                value=is_selected,
                key=f"sitemap_{i}"
            ):
                if sitemap["url"] not in st.session_state.selected_sitemaps:
                    st.session_state.selected_sitemaps.append(sitemap["url"])
            else:
                if sitemap["url"] in st.session_state.selected_sitemaps:
                    st.session_state.selected_sitemaps.remove(sitemap["url"])
        
        # Bouton pour utiliser les sitemaps sélectionnés
        col1, _ = st.columns([1, 3])
        with col1:
            if st.button("Extract from Selected Sitemaps", type="primary"):
                if st.session_state.selected_sitemaps:
                    # On remplit le champ de saisie des sitemaps
                    st.session_state.sitemap_input = "\n".join(st.session_state.selected_sitemaps)
                    # On change le mode d'entrée pour "XML Sitemaps"
                    st.session_state.input_type = "XML Sitemaps"
                    st.rerun()
                else:
                    st.warning("⚠️ Please select at least one sitemap.")

def display():
    """Affiche l'onglet extraction."""
    initialize_sitemap_discovery()
    
    st.markdown("""
    This application extracts iframes from the path `//body/div/div/main/` 
    that start with `https://ovh.slgnt.eu/optiext/`.
    """)

    # Définir le type d'entrée
    if 'input_type' not in st.session_state:
        st.session_state.input_type = "XML Sitemaps"
    
    # Définir la valeur du champ des sitemaps
    if 'sitemap_input' not in st.session_state:
        st.session_state.sitemap_input = ""

    input_type = st.radio(
        "Input type:",
        ["Discover Sitemaps", "XML Sitemaps", "URLs List"]
    )
    
    # Mettre à jour le type d'entrée en session
    st.session_state.input_type = input_type

    if input_type == "Discover Sitemaps":
        display_sitemap_discovery()
        return
    
    col1, col2 = st.columns([2, 1])

    with col1:
        if input_type == "XML Sitemaps":
            urls_input = st.text_area(
                "Sitemap URLs (one per line):",
                value=st.session_state.sitemap_input,
                placeholder="https://example.com/sitemap.xml",
                height=200
            )
        else:
            urls_input = st.text_area(
                "URLs to analyze (one per line):",
                placeholder="https://example.com/page1",
                height=200
            )

    urls = [url.strip() for url in urls_input.splitlines() if url.strip()]

    col1, _ = st.columns([1, 3])
    with col1:
        start_extraction = st.button("Extract iframes", type="primary")

    if start_extraction:
        if not urls:
            st.warning("⚠️ Please enter at least one URL.")
            return

        with st.spinner("🔄 Processing..."):
            start_time = time.time()
            results = []
            processed_urls = []

            if input_type == "XML Sitemaps":
                status_sitemap = st.empty()
                progress_sitemap = st.progress(0)

                sitemap_extractor = SitemapExtractor()
                for idx, sitemap_url in enumerate(urls):
                    status_sitemap.write(f"📑 Reading sitemap: {sitemap_url}")
                    sitemap_urls = sitemap_extractor.extract_urls(sitemap_url)
                    processed_urls.extend(sitemap_urls)
                    progress_sitemap.progress((idx + 1) / len(urls))

                if processed_urls:
                    st.success(f"✅ {len(processed_urls)} URLs extracted from sitemaps")
                else:
                    st.error("❌ No URLs found in sitemaps")
                    return
            else:
                processed_urls = urls

            if Config.TEST_MODE and Config.TEST_SIZE and len(processed_urls) > Config.TEST_SIZE:
                st.info(f"🧪 Test mode enabled: randomly selecting {Config.TEST_SIZE} URLs")
                processed_urls = random.sample(processed_urls, Config.TEST_SIZE)

            if processed_urls:
                status = st.empty()
                progress = st.progress(0)
                status.write(f"🔍 Analyzing {len(processed_urls)} URLs...")

                for i in range(0, len(processed_urls), Config.CHUNK_SIZE):
                    chunk = processed_urls[i:i + Config.CHUNK_SIZE]
                    status.write(f"🔍 Processing batch {i//Config.CHUNK_SIZE + 1}/{len(processed_urls)//Config.CHUNK_SIZE + 1}")
                    chunk_results = process_urls_batch(chunk, progress)
                    results.extend(chunk_results)

                if results:
                    execution_time = time.time() - start_time
                    # Réinitialiser l'analyse précédente
                    st.session_state.analyzed_df = None
                    # Mettre à jour les résultats d'extraction
                    st.session_state.extraction_results = results

                    parameters = {
                        "test_mode": Config.TEST_MODE,
                        "test_urls": Config.TEST_SIZE if Config.TEST_MODE else None,
                        "workers": Config.MAX_WORKERS,
                        "timeout": Config.TIMEOUT,
                        "chunk_size": Config.CHUNK_SIZE
                    }
                    from .history_tab import save_to_history
                    save_to_history(results, urls, parameters, execution_time)

                    st.success(f"""
                    ✨ Extraction completed in {execution_time:.2f} seconds!
                    - 📊 {len(processed_urls)} URLs analyzed
                    - 🎯 {len(results)} iframes found
                    """)
                    
                    st.info("💡 Go to the **Analysis** tab for a complete analysis!")
                else:
                    st.info("ℹ️ No iframes found.")