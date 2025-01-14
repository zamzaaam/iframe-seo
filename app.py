import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time

# Function to fetch the Featured Snippet content
def fetch_featured_snippet_with_xpath(keyword, xpath):
    # Configure Selenium WebDriver
    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")  # Run without opening the browser
    options.add_argument("--disable-gpu")
    
    # Start the WebDriver
    driver = webdriver.Firefox(service=Service(ChromeDriverManager().install()), options=options)
    url = f"https://www.google.com/search?q={keyword}"
    driver.get(url)
    time.sleep(2)  # Wait for the page to load
    
    try:
        # Locate the Featured Snippet using XPath
        snippet = driver.find_element(By.XPATH, xpath)
        content = snippet.text
    except Exception as e:
        content = f"Error: {str(e)}. No Featured Snippet found."
    
    driver.quit()  # Close the browser
    return content

# Streamlit UI
st.title("Extract Google Featured Snippet Text Using XPath")
keyword = st.text_input("Enter a keyword (e.g., 'vps'):")
xpath = st.text_input(
    "Enter the XPath for the Featured Snippet (default provided):",
    value="/html/body/div[3]/div/div[13]/div[1]/div[2]/div/div/div[1]/div/div/div[1]/div/div[1]/block-component/div/div[1]/div/div/div/div/div[1]/div/div/div/div/div[1]/div"
)

if st.button("Extract Featured Snippet"):
    result = fetch_featured_snippet_with_xpath(keyword, xpath)
    st.subheader("Featured Snippet Content:")
    st.write(result)
