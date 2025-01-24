import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
import csv
from io import StringIO

# Regex pour extraire les liens d'iframes
IFRAME_REGEX = r'<iframe[^>]*src=["\']([^"\']+)["\']'

# Fonction pour extraire les liens iframe d'une URL
def extract_iframe_links(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Extraire uniquement le contenu de la balise <body>
            body = soup.find("body")
            if not body:
                return []
            
            # Exclure les iframes présents dans des balises <nav> (menu) ou <footer>
            excluded_sections = body.find_all(["nav", "footer"])
            for section in excluded_sections:
                section.decompose()  # Supprimer ces sections du DOM
            
            # Extraire les liens <iframe> restants dans le body
            iframes = body.find_all("iframe")
            iframe_links = [iframe.get("src") for iframe in iframes if iframe.get("src")]
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
            # Utiliser le parser lxml pour lire les sitemaps XML
            soup = BeautifulSoup(response.content, "lxml")
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
            # Barre de progression
            progress_bar = st.progress(0)
            total_urls = len(processed_urls)

            for idx, url in enumerate(processed_urls, start=1):
                # Analyse de chaque page
                iframe_links = extract_iframe_links(url)
                for iframe_link in iframe_links:
                    results.append((url, iframe_link))

                # Mise à jour de la barre de progression
                progress_bar.progress(idx / total_urls)

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

            # Création du CSV
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=["From", "Iframe Link", "Usage Count"], quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(enriched_results)
            csv_data = output.getvalue()

            # Bouton de téléchargement
            st.download_button(
                label="Télécharger les résultats en CSV",
                data=csv_data,
                file_name="iframe_links_with_usage_count.csv",
                mime="text/csv",
            )

            # Affichage des résultats
            st.success(f"Extraction terminée ! {len(enriched_results)} liens d'iframes trouvés.")
            st.markdown("### Résultats")
            st.table(enriched_results)
