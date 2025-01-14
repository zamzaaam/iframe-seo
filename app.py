import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time

# Function to extract Featured Snippet content
def fetch_featured_snippet_content(keyword):
    # Configure the Selenium WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run browser in headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Start the WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    url = f"https://www.google.com/search?q={keyword}"
    driver.get(url)
    time.sleep(2)  # Allow time for the page to load

    try:
        # Locate the Featured Snippet content
        snippet = driver.find_element(By.CSS_SELECTOR, "div[data-attrid='wa:/description']")
        content = snippet.text
    except Exception as e:
        content = f"Error: {str(e)} or no Featured Snippet content found."
    
    driver.quit()  # Close the WebDriver
    return content

# Streamlit UI
st.title("Extract Google Featured Snippet Content")
keyword = st.text_input("Enter a keyword (e.g., 'web hosting'):")

if st.button("Extract Featured Snippet Content"):
    result = fetch_featured_snippet_content(keyword)
    st.subheader("Featured Snippet Content:")
    st.write(result)
