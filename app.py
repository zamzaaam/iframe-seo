import streamlit as st
from bs4 import BeautifulSoup
import requests

# Fonction pour récupérer une Featured Snippet de Google
def fetch_featured_snippet(keyword):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/111.0.0.0 Safari/537.36"
        )
    }
    url = f"https://www.google.com/search?q={keyword}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        # Rechercher la classe contenant la Featured Snippet
        snippet = soup.find("div", {"class": "wDYxhc"})
        if snippet:
            return snippet.get_text(strip=True)
        else:
            return "Aucune Featured Snippet trouvée pour cette requête."
    else:
        return f"Erreur : impossible de se connecter à Google (status code {response.status_code})."

# Interface Streamlit
st.title("Extraction de Featured Snippets")
keyword = st.text_input("Entrez un mot-clé pour récupérer une Featured Snippet (ex. 'hébergement web') :")
if st.button("Extraire la Featured Snippet"):
    result = fetch_featured_snippet(keyword)
    st.subheader("Résultat :")
    st.write(result)
