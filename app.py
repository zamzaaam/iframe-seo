import streamlit as st
import requests
import re
from bs4 import BeautifulSoup

# Regex pour extraire les liens d'iframes
IFRAME_REGEX = r'<iframe[^>]*src=["\']([^"\']+)["\']'

# Fonction pour extraire les liens iframe d'une URL
def extract_iframe_links(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            html_content = response.text
            iframe_links = re.findall(IFRAME_REGEX, html_content)
            return iframe_links
        else:
            return []
    except Exception as e:
        st.warning(f"Erreur pour {url}: {e}")
        return []

# Fonction pour extraire toutes les URLs des sitemaps
def extract_urls_from_sitemap(sitemap_url):
    try:
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "xml")
            urls = [loc.text for loc in soup.find_all("loc")]
            return urls
        else:
            st.warning(f"Impossible d'accéder au sitemap : {sitemap_url}")
            return []
    except Exception as e:
        st.warning(f"Erreur avec le sitemap {sitemap_url}: {e}")
        return []

# Streamlit app
st.title("Extraction des liens d'iframes")
st.markdown("Cette application extrait les liens contenus dans les balises `<iframe>` d'une ou plusieurs pages web.")

# Récupérer le type d'entrée de l'utilisateur
input_type = st.radio("Fournissez une source : ", ["Sitemaps XML", "Liste d'URLs"])

# Initialisation des résultats
results = []

if input_type:
    if input_type == "Sitemaps XML":
        sitemap_urls = st.text_area(
            "Entrez les URLs des sitemaps XML (une URL par ligne) :",
            placeholder="https://example.com/sitemap.xml",
        ).splitlines()
        sitemap_urls = [url.strip() for url in sitemap_urls if url.strip()]
    else:
        urls = st.text_area(
            "Entrez les URLs (une URL par ligne) :",
            placeholder="https://example.com/page1",
        ).splitlines()
        urls = [url.strip() for url in urls if url.strip()]

    # Lancer l'extraction si des URLs sont fournies
    if st.button("Extraire les liens d'iframes"):
        processed_urls = []

        if input_type == "Sitemaps XML":
            for sitemap_url in sitemap_urls:
                st.info(f"Extraction des URLs du sitemap : {sitemap_url}")
                urls_from_sitemap = extract_urls_from_sitemap(sitemap_url)
                processed_urls.extend(urls_from_sitemap)
        else:
            processed_urls = urls

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

            # Comptabilisation des occurrences
            iframe_usage_count = {}
            for _, iframe_link in results:
                iframe_usage_count[iframe_link] = iframe_usage_count.get(iframe_link, 0) + 1

            # Enrichissement des résultats
            enriched_results = [
                {"From": row[0], "Iframe Link": row[1], "Usage Count": iframe_usage_count[row[1]]}
                for row in results
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
