if results:
    # Nettoyage des résultats pour éviter les problèmes de séparation
    clean_results = []
    iframe_usage_count = {}

    # Comptabiliser les occurrences des liens iframe
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

    st.success(f"Extraction terminée ! {len(enriched_results)} liens d'iframes trouvés.")
    st.markdown("### Résultats")

    # Affichage sous forme de tableau enrichi
    st.table(enriched_results)

    # Téléchargement en CSV avec la nouvelle colonne
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
