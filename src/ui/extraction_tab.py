import streamlit as st
from ..config import Config
from ..extractors import SitemapExtractor, IframeExtractor
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

def display():
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
