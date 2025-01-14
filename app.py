import streamlit as st
import requests
from bs4 import BeautifulSoup
import urllib.parse
import pandas as pd

# Must be the first Streamlit command
st.set_page_config(page_title="SERP Similarity Analysis", layout="centered")

# Purpose of the tool
st.write("## Purpose")
st.write("This tool compares the similarity of SERPs (Search Engine Results Pages) for two different keywords. It helps determine whether a new page should be created or if an existing page should be optimized based on the overlap of search results.")

# Disclaimer
st.info("**Disclaimer:** Optimizing titles alone is not enough for SEO. Ensure you're addressing other key factors like content quality, backlinks, and user experience.")

# Backlink to Charles Migaud's site
st.markdown('Tool made with ❤️ by [Charles Migaud](https://charles-migaud.fr)')

def scrape_serp(keyword, language, country, num_results):
    query = urllib.parse.quote(keyword)
    url = f"https://www.google.com/search?q={query}&hl={language}&gl={country}&num={num_results}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, KHTML, Gecko) Chrome/116.0.5845.96 Safari/537.36"
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        st.error("Error while fetching results.")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')

    results = []
    for g in soup.find_all('div', class_='g')[:num_results]:
        link = g.find('a', href=True)
        if link:
            title = g.find('h3').get_text() if g.find('h3') else "Title not found"
            results.append((link['href'], title))

    return results

def extract_domain(url):
    """Extract domain name from URL."""
    parsed_url = urllib.parse.urlparse(url)
    return parsed_url.netloc

def analyze_titles(results, keyword1, keyword2):
    counts = {
        "common_keyword1": 0,
        "common_keyword2": 0,
        "common_both": 0,
    }

    urls_common = {url: title for url, title in results[0]}
    urls_non_common = {url: title for url, title in results[1]}

    for url, title in urls_common.items():
        if keyword1.lower() in title.lower() and keyword2.lower() in title.lower():
            counts["common_both"] += 1
        elif keyword1.lower() in title.lower():
            counts["common_keyword1"] += 1
        elif keyword2.lower() in title.lower():
            counts["common_keyword2"] += 1

    return counts

def calculate_similarity(results1, results2):
    # Extract full URLs
    urls1 = {result[0]: result[1] for result in results1}
    urls2 = {result[0]: result[1] for result in results2}

    # Calculate similarity for URLs
    common_urls = set(urls1.keys()).intersection(set(urls2.keys()))
    total_urls = len(set(urls1.keys()).union(set(urls2.keys())))

    similarity_rate_url = (len(common_urls) / total_urls) * 100 if total_urls > 0 else 0
    
    return common_urls, urls1, urls2, similarity_rate_url

# User Interface with Streamlit
st.title("SERP Similarity Analysis")
st.markdown("---")

# Input fields for keywords
col1, col2 = st.columns(2)

with col1:
    keyword1 = st.text_input("Enter Keyword 1:", placeholder="Ex: vps")
    language1 = st.selectbox("Language (Keyword 1):", ["fr", "en", "es", "de", "it", "pt", "pl"])
    country1 = st.selectbox("Country (Keyword 1):", ["FR", "GB", "US", "CA", "ES", "DE", "IT", "PT", "PL", "MA", "SN", "TN"])

with col2:
    keyword2 = st.text_input("Enter Keyword 2:", placeholder="Ex: virtual private server")
    language2 = st.selectbox("Language (Keyword 2):", ["fr", "en", "es", "de", "it", "pt", "pl"])
    country2 = st.selectbox("Country (Keyword 2):", ["FR", "GB", "US", "CA", "ES", "DE", "IT", "PT", "PL", "MA", "SN", "TN"])

# Slider to choose the number of URLs to scrape
num_urls = st.slider("Select the number of URLs to scrape (between 10 and 100):", min_value=10, max_value=100, value=10, step=10)

st.markdown("---")

if st.button("Analyze"):
    if keyword1 and keyword2:
        # Scrape the results for both keywords
        results_keyword1 = scrape_serp(keyword1, language1, country1, num_urls)
        results_keyword2 = scrape_serp(keyword2, language2, country2, num_urls)

        # Calculate similarity
        common_urls, urls1, urls2, similarity_rate_url = calculate_similarity(results_keyword1, results_keyword2)

        # Analyze titles
        counts = analyze_titles((results_keyword1, results_keyword2), keyword1, keyword2)

        # Display results
        st.write(f"**Similarity Rate URL: {similarity_rate_url:.2f}%**")

        if counts['common_both'] > 0:
            st.success("The two keywords seem to contribute to a common URL in the title.")
        elif keyword1 in keyword2:
            st.warning(f"**{keyword2}** is more specific than **{keyword1}**. Consider using the more specific keyword to better target your audience.")
        elif counts['common_keyword1'] > counts['common_keyword2']:
            st.warning(f"It is better to include **{keyword1}** in your title to optimise your ranking.")
        elif counts['common_keyword2'] > counts['common_keyword1']:
            st.warning(f"It's better to include **{keyword2}** in your title to optimise your ranking.")
        else:
            st.info("None of the keywords seem to be effective on their own. Consider other optimisations.")

        st.markdown("---")
        st.subheader("SERP Results")

        # Display search links with encoded keywords and the correct language/country
        encoded_keyword1 = urllib.parse.quote(keyword1)
        encoded_keyword2 = urllib.parse.quote(keyword2)

        # Generate SERP links with language and country parameters
        serp_url1 = f"https://www.google.com/search?q={encoded_keyword1}&hl={language1}&gl={country1}&num={num_urls}"
        serp_url2 = f"https://www.google.com/search?q={encoded_keyword2}&hl={language2}&gl={country2}&num={num_urls}"

        # Display the clickable links for the SERPs
        st.markdown(f"[View SERP for Keyword: {keyword1}]({serp_url1})")
        st.markdown(f"[View SERP for Keyword: {keyword2}]({serp_url2})")

        # Display SERP results
        with st.expander(f"Details for Keyword: {keyword1}"):
            st.write(f"**SERP for Keyword: {keyword1}**")
            for rank, (url, title) in enumerate(results_keyword1, start=1):
                st.markdown(f"{rank}. [{title}]({url})")

        with st.expander(f"Details for Keyword: {keyword2}"):
            st.write(f"**SERP for Keyword: {keyword2}**")
            for rank, (url, title) in enumerate(results_keyword2, start=1):
                st.markdown(f"{rank}. [{title}]({url})")

        # Prepare data for the table
        common_urls_data = []
        for url in common_urls:
            rank_keyword1 = next((i + 1 for i, (u, _) in enumerate(results_keyword1) if u == url), "Not Found")
            rank_keyword2 = next((i + 1 for i, (u, _) in enumerate(results_keyword2) if u == url), "Not Found")
            common_urls_data.append({"URL": url, f"Rank in '{keyword1}'": rank_keyword1, f"Rank in '{keyword2}'": rank_keyword2})

        # Display number of common URLs
        st.write(f"**Number of Common URLs: {len(common_urls)}**")

        # Create a DataFrame for exporting to CSV
        df_common = pd.DataFrame(common_urls_data)

        # Button to download the common data as CSV
        st.download_button(
            label="Download Common URLs CSV",
            data=df_common.to_csv(index=False).encode('utf-8'),
            file_name='common_urls.csv',
            mime='text/csv',
        )

        # Display common URLs in a table
        st.dataframe(df_common)

    else:
        st.error("Please enter both keywords.")

