import streamlit as st
from ..config import Config
from ..extractors import SitemapExtractor, IframeExtractor, SitemapDiscoveryExtractor
from ..utils import is_valid_url, sanitize_urls, sanitize_html
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_urls_batch(urls, progress_bar):
    results = []
    extractor = IframeExtractor()
    completed_urls = 0

    # Validation des URLs avant traitement
    urls = sanitize_urls(urls)
    
    if not urls:
        return []

    # Vérifier l'état d'arrêt avant de commencer le traitement
    if st.session_state.abort_extraction:
        progress_bar.progress(1.0)  # Compléter la barre de progression
        st.warning("⚠️ Extraction aborted by user!")
        return []

    with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
        future_to_url = {
            executor.submit(extractor.extract_from_url, url): url
            for url in urls
        }

        for future in as_completed(future_to_url):
            # Vérifier si l'extraction doit être interrompue
            if st.session_state.abort_extraction:
                # Annuler les futures en attente
                for f in future_to_url:
                    if not f.done():
                        f.cancel()
                st.warning("⚠️ Extraction aborted by user!")
                break
            
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
    
    # Validation de l'URL
    if base_url and not is_valid_url(base_url):
        st.error("⚠️ Invalid URL format. Please enter a valid URL starting with http:// or https://")
        base_url = None
    
    col1, col2 = st.columns([1, 1])
    with col1:
        discover_button = st.button("🔍 Discover Sitemaps", type="primary")
    
    # Ajout du bouton d'arrêt dans la section de découverte de sitemap
    with col2:
        if st.button("🛑 STOP DISCOVERY", 
                   type="secondary", 
                   help="Immediately stops the sitemap discovery",
                   use_container_width=True):
            st.session_state.abort_extraction = True
            st.warning("⚠️ Discovery abort requested. Please wait for current operations to finish...")
            st.rerun()
    
    if discover_button and base_url:
        # Réinitialiser l'état d'arrêt avant de commencer
        st.session_state.abort_extraction = False
        
        with st.spinner("🔄 Discovering sitemaps..."):
            # Effectuer la découverte
            discovery_extractor = SitemapDiscoveryExtractor()
            discovered = discovery_extractor.discover_sitemaps(base_url)
            
            # Vérifier si la découverte a été interrompue
            if st.session_state.abort_extraction:
                st.warning("⚠️ Sitemap discovery aborted by user!")
                return
            
            if discovered:
                # Valider chaque URL de sitemap avant de les stocker
                valid_sitemaps = []
                for sitemap in discovered:
                    if is_valid_url(sitemap["url"]):
                        valid_sitemaps.append(sitemap)
                
                st.session_state.discovered_sitemaps = valid_sitemaps
                # Par défaut, tout sélectionner
                st.session_state.selected_sitemaps = [s["url"] for s in valid_sitemaps]
                st.success(f"✅ Found {len(valid_sitemaps)} sitemaps!")
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
            
            # Sanitize the URL for display to prevent XSS
            display_url = sanitize_html(sitemap["url"])
            
            # Cases à cocher
            is_selected = sitemap["url"] in st.session_state.selected_sitemaps
            if st.checkbox(
                f"{prefix}{icon} {display_url}",
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
                    # Valider à nouveau les URLs avant de les utiliser
                    valid_urls = sanitize_urls(st.session_state.selected_sitemaps)
                    # On remplit le champ de saisie des sitemaps
                    st.session_state.sitemap_input = "\n".join(valid_urls)
                    # On change le mode d'entrée pour "XML Sitemaps"
                    st.session_state.input_type = "XML Sitemaps"
                    st.rerun()
                else:
                    st.warning("⚠️ Please select at least one sitemap.")

def display():
    """Affiche l'onglet extraction."""
    initialize_sitemap_discovery()
    
    # Si un arrêt a été demandé, afficher un message
    if st.session_state.abort_extraction:
        st.error("⚠️ Extraction was aborted by user. You can start a new extraction below.")
    
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

    # Extraction et validation des URLs
    raw_urls = [url.strip() for url in urls_input.splitlines() if url.strip()]
    
    # MODIFICATION: Éliminer les doublons des URLs d'entrée
    raw_urls = list(dict.fromkeys(raw_urls))
    
    urls = sanitize_urls(raw_urls)
    
    # Avertissement si des URLs ont été filtrées
    if len(urls) < len(raw_urls):
        st.warning(f"⚠️ {len(raw_urls) - len(urls)} invalid URLs have been filtered out. Please check your input.")

    col1, col2 = st.columns([1, 1])
    with col1:
        start_extraction = st.button("Extract iframes", type="primary")
    
    # Ajout du bouton d'arrêt dans l'onglet d'extraction
    with col2:
        if st.button("🛑 STOP EXTRACTION", 
                   type="secondary", 
                   help="Immediately stops the current extraction",
                   use_container_width=True):
            st.session_state.abort_extraction = True
            st.warning("⚠️ Extraction abort requested. Please wait for current operations to finish...")
            st.rerun()

    if start_extraction:
        # Réinitialiser l'état d'arrêt avant de commencer
        st.session_state.abort_extraction = False
        
        if not urls:
            st.warning("⚠️ Please enter at least one valid URL.")
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
                    # Vérifier si l'extraction doit être interrompue
                    if st.session_state.abort_extraction:
                        progress_sitemap.progress(1.0)
                        st.warning("⚠️ Sitemap extraction aborted by user!")
                        return
                    
                    status_sitemap.write(f"📑 Reading sitemap: {sanitize_html(sitemap_url)}")
                    sitemap_urls = sitemap_extractor.extract_urls(sitemap_url)
                    # Valider les URLs extraites du sitemap
                    sitemap_urls = sanitize_urls(sitemap_urls)
                    
                    # MODIFICATION: Ajouter uniquement les URLs non-dupliquées
                    for url in sitemap_urls:
                        if url not in processed_urls:
                            processed_urls.append(url)
                    
                    progress_sitemap.progress((idx + 1) / len(urls))

                if processed_urls and not st.session_state.abort_extraction:
                    st.success(f"✅ {len(processed_urls)} unique URLs extracted from sitemaps")
                else:
                    st.error("❌ No valid URLs found in sitemaps")
                    return
            else:
                processed_urls = urls

            if Config.TEST_MODE and Config.TEST_SIZE and len(processed_urls) > Config.TEST_SIZE:
                st.info(f"🧪 Test mode enabled: randomly selecting {Config.TEST_SIZE} URLs")
                processed_urls = random.sample(processed_urls, Config.TEST_SIZE)

            if processed_urls and not st.session_state.abort_extraction:
                status = st.empty()
                progress = st.progress(0)
                status.write(f"🔍 Analyzing {len(processed_urls)} URLs...")

                # Afficher le nombre d'URLs uniques
                st.info(f"🔍 Found {len(processed_urls)} unique URLs to analyze")

                for i in range(0, len(processed_urls), Config.CHUNK_SIZE):
                    # Vérifier si l'extraction doit être interrompue
                    if st.session_state.abort_extraction:
                        progress.progress(1.0)
                        st.warning("⚠️ URL batch processing aborted by user!")
                        break
                    
                    chunk = processed_urls[i:i + Config.CHUNK_SIZE]
                    status.write(f"🔍 Processing batch {i//Config.CHUNK_SIZE + 1}/{len(processed_urls)//Config.CHUNK_SIZE + 1}")
                    chunk_results = process_urls_batch(chunk, progress)
                    results.extend(chunk_results)

                if results and not st.session_state.abort_extraction:
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
                    - 📊 {len(processed_urls)} unique URLs analyzed
                    - 🎯 {len(results)} iframes found
                    """)
                    
                    st.info("💡 Go to the **Analysis** tab for a complete analysis!")
                elif st.session_state.abort_extraction:
                    # Si l'extraction a été interrompue
                    execution_time = time.time() - start_time
                    if results:
                        # Sauvegarder quand même les résultats partiels si il y en a
                        st.session_state.extraction_results = results
                        parameters = {
                            "test_mode": Config.TEST_MODE,
                            "test_urls": Config.TEST_SIZE if Config.TEST_MODE else None,
                            "workers": Config.MAX_WORKERS,
                            "timeout": Config.TIMEOUT,
                            "chunk_size": Config.CHUNK_SIZE,
                            "aborted": True
                        }
                        from .history_tab import save_to_history
                        save_to_history(results, urls, parameters, execution_time)
                        
                        st.warning(f"""
                        ⚠️ Extraction was aborted after {execution_time:.2f} seconds.
                        - Only {len(results)} iframes were found before abort.
                        - Partial results are still available for analysis.
                        """)
                    else:
                        st.error("❌ Extraction was aborted. No iframes were found.")
                else:
                    st.info("ℹ️ No iframes found.")