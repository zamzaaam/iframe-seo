if input_type == "Sitemaps XML":
    processed_urls = []
    for sitemap_url in sitemap_urls:
        st.info(f"Extraction des URLs du sitemap : {sitemap_url}")
        urls_from_sitemap = extract_urls_from_sitemap(sitemap_url)
        processed_urls.extend(urls_from_sitemap)
else:
    processed_urls = urls

# Vérifier si processed_urls est vide
if not processed_urls:
    st.warning("Aucune URL à traiter. Veuillez entrer des sitemaps ou des URLs.")
else:
    for url in processed_urls:
        st.info(f"Analyse de la page : {url}")
        iframe_links = extract_iframe_links(url)
        for iframe_link in iframe_links:
            results.append((url, iframe_link))

    # Déduplication des résultats
    results = list(set(results))

    # Afficher les résultats
    if results:
        st.success(f"Extraction terminée ! {len(results)} liens d'iframes trouvés.")
        st.markdown("### Résultats")
        for from_url, iframe_link in results:
            st.write(f"- **From:** {from_url}")
            st.write(f"  - **Iframe Link:** {iframe_link}")
        st.download_button(
            label="Télécharger les résultats en CSV",
            data="\n".join([f"{from_url},{iframe_link}" for from_url, iframe_link in results]),
            file_name="iframe_links.csv",
            mime="text/csv",
        )
    else:
        st.warning("Aucun lien d'iframe trouvé.")
