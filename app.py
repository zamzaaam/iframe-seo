import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
import pandas as pd

# Regex pour extraire les liens des iframes
IFRAME_REGEX = r'<iframe[^>]*src=["\']([^"\']+)["\']'

# Fonction pour extraire les URLs des iframes d'une page web
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

# Fonction pour extraire toutes les URLs d'un sitemap
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
st.markdown(
    """
    Cette application extrait les liens contenus dans les balises `<iframe>` d'une ou plusieurs pages web.
    Vous pouvez fournir un ou plusieurs **sitemaps XML** ou une **liste d'URLs**.
    """
)

# Input pour les URLs ou sitemaps
input_type = st.radio("Fournissez une source : ", ["Sitemaps XML", "Liste d'URLs"])

if input_type == "Sitemaps XML":
    sitemap_urls = st.text_area(
        "Entrez les URLs des sitemaps XML (une URL par ligne) :",
        placeholder="Exemple : https://example.com/sitemap.xml",
    ).splitlines()
    sitemap_urls = [url.strip() for url in sitemap_urls if url.strip()]
else:
    urls = st.text_area(
        "Entrez les URLs (une URL par ligne) :",
        placeholder="Exemple : https://example.com/page1",
    ).splitlines()
    urls = [url.strip() for url in urls if url.strip()]

# Bouton pour lancer l'extraction
if st.button("Extraire les liens d'iframes"):
    all_iframe_links = []
    processed_urls = []

    if input_type == "Sitemaps XML":
        # Extraire les URLs des sitemaps
        for sitemap_url in sitemap_urls:
            st.info(f"Extraction des URLs du sitemap : {sitemap_url}")
            urls_from_sitemap = extract_urls_from_sitemap(sitemap_url)
            processed_urls.extend(urls_from_sitemap)
    else:
        processed_urls = urls

    # Extraire les liens des iframes pour chaque URL
    for url in processed_urls:
        st.info(f"Analyse de la page : {url}")
        iframe_links = extract_iframe_links(url)
        for iframe_link in iframe_links:
            all_iframe_links.append({"from": url, "iframe_link": iframe_link})

    # Créer un tableau des résultats
    if all_iframe_links:
        df = pd.DataFrame(all_iframe_links, columns=["from", "iframe_link"])
        st.success(f"Extraction terminée ! {len(all_iframe_links)} liens d'iframes trouvés.")
        st.dataframe(df)
        st.download_button(
            label="Télécharger les résultats en CSV",
            data=df.to_csv(index=False),
            file_name="iframe_links.csv",
            mime="text/csv",
        )
    else:
        st.warning("Aucun lien d'iframe trouvé.")
