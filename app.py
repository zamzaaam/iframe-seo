import streamlit as st
from bs4 import BeautifulSoup
import requests
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize

# Téléchargement des ressources NLTK nécessaires
nltk.download("punkt", quiet=True)

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

# Fonction pour analyser le texte de l'utilisateur
def analyze_text(text):
    words = word_tokenize(text)
    sentences = sent_tokenize(text)
    word_count = len(words)
    sentence_count = len(sentences)
    pixel_estimate = len(text) * 7  # Estimation approximative : 7px par caractère
    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "pixel_estimate": pixel_estimate,
    }

# Fonction pour effectuer une analyse sémantique
def semantic_analysis(text1, text2):
    vectorizer = CountVectorizer().fit_transform([text1, text2])
    vectors = vectorizer.toarray()
    cosine_sim = cosine_similarity(vectors)
    return cosine_sim[0][1]

# Interface utilisateur avec Streamlit
st.title("Outil d'Optimisation des Featured Snippets")

# Étape 1 : Récupérer ou coller une Featured Snippet
st.header("Étape 1 : Récupérer ou Coller une Featured Snippet")
keyword = st.text_input("Entrez un mot-clé pour récupérer la Featured Snippet :")
if st.button("Récupérer la Featured Snippet"):
    snippet = fetch_snippet(keyword)
    if snippet:
        st.success(f"Featured Snippet trouvée :\n{snippet}")
    else:
        st.error("Aucune Featured Snippet trouvée pour ce mot-clé.")
else:
    snippet = st.text_area("Ou collez le texte de la Featured Snippet existante ici :")

# Étape 2 : Analyse du texte de l'utilisateur
st.header("Étape 2 : Analyse de votre Texte")
user_text = st.text_area("Entrez votre texte proposé :")
if st.button("Analyser le Texte"):
    if user_text:
        analysis = analyze_text(user_text)
        st.write(f"Nombre de mots : {analysis['word_count']}")
        st.write(f"Nombre de phrases : {analysis['sentence_count']}")
        st.write(f"Taille estimée en pixels : {analysis['pixel_estimate']} px")
    else:
        st.error("Veuillez fournir un texte pour l'analyse.")

# Étape 3 : Analyse sémantique
if snippet and user_text:
    st.header("Étape 3 : Analyse Sémantique")
    similarity = semantic_analysis(snippet, user_text)
    st.write(f"Similarité Sémantique (0 à 1) : {similarity:.2f}")
