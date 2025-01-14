import streamlit as st
from bs4 import BeautifulSoup
import requests

# Fonction pour récupérer la Featured Snippet
def fetch_snippet(keyword):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.google.com/search?q={keyword}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        snippet = soup.find("div", class_="BNeawe").text if soup.find("div", class_="BNeawe") else None
        return snippet
    else:
        return None

# Interface utilisateur avec Streamlit
st.title("Outil minimaliste pour Featured Snippet")

keyword = st.text_input("Entrez un mot-clé pour récupérer la Featured Snippet :")
if st.button("Récupérer la Featured Snippet"):
    snippet = fetch_snippet(keyword)
    if snippet:
        st.success(f"Featured Snippet trouvée :\n{snippet}")
    else:
        st.error("Aucune Featured Snippet trouvée pour ce mot-clé.")
