import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time

# Fonction pour récupérer une Featured Snippet avec Selenium
def fetch_featured_snippet(keyword):
    # Configurer le pilote Chrome
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Exécuter sans ouvrir une fenêtre
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Lancer le navigateur
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    url = f"https://www.google.com/search?q={keyword}"
    driver.get(url)
    time.sleep(2)  # Attendre que la page se charge
    
    try:
        # Rechercher la Featured Snippet
        snippet = driver.find_element(By.CLASS_NAME, "wDYxhc")
        result = snippet.text
    except Exception as e:
        result = "Aucune Featured Snippet trouvée ou erreur : " + str(e)
    
    driver.quit()  # Fermer le navigateur
    return result

# Interface utilisateur Streamlit
st.title("Extraction de Featured Snippets avec Selenium")
keyword = st.text_input("Entrez un mot-clé (ex. 'hébergement web') :")
if st.button("Extraire la Featured Snippet"):
    result = fetch_featured_snippet(keyword)
    st.subheader("Résultat :")
    st.write(result)
