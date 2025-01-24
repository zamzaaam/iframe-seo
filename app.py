# Initialisation de la variable results
results = []

if input_type == "Sitemaps XML":
    processed_urls = []
    for sitemap_url in sitemap_urls:
        st.info(f"Extraction des URLs du sitemap : {sitemap_url}")
        urls_from_sitemap = extract_urls_from_sitemap(sitemap_url)
        processed_urls.extend(urls_from_sitemap)
else:
    processed_urls = urls

# Vérifiez si processed_urls est vide
if not processed_urls:
    st.warning("Aucune URL à traiter. Veuillez entrer des sitemaps ou des URLs.")
else:
    for url in processed_urls:
        st.info(f"Analyse de la page : {url}")
        iframe_links = extract_iframe_links(url)
        for iframe_link in iframe_links:
            results.append((url, iframe_link))

    # Vérifiez si des résultats ont été trouvés
    if results:
        # Déduplication des résultats
        results = list(set(results))

        # Nettoyage des résultats et comptage
        clean_results = []
        iframe_usage_count = {}

        for from_url, iframe_link in results:
            iframe_link = iframe_link.replace("&amp;", "&")  # Nettoyage des entités HTML
            clean_results.append((from_url, iframe_link))
            if iframe_link in iframe_usage_count:
                iframe_usage_count[iframe_link] += 1
            else:
                iframe_usage_count[iframe_link] = 1

        # Ajouter une colonne pour le nombre d'utilisations
        enriched_results = [
            {"From": row[0], "Iframe Link": row[1], "Usage Count": iframe_usage_count[row[1]]}
            for row in clean_results
        ]

        # Affichage des résultats
        st.success(f"Extraction terminée ! {len(enriched_results)} liens d'iframes trouvés.")
        st.markdown("### Résultats")
        st.table(enriched_results)

        # Téléchargement en CSV
        csv_data = "From,Iframe Link,Usage Count\n" + "\n".join(
            [f"{row['From']},{row['Iframe Link']},{row['Usage Count']}" for row in enriched_results]
        )
        st.download_button(
            label="Télécharger les résultats en CSV",
            data=csv_data,
            file_name="iframe_links_with_usage_count.csv",
            mime="text/csv",
        )
    else:
        st.warning("Aucun lien d'iframe trouvé.")
