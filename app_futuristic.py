import os, sqlite3, uuid, requests
from datetime import datetime
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from textblob import TextBlob
import nltk

# Download punkt for TextBlob
nltk.download('punkt')

# -----------------------------
# SETUP
# -----------------------------
# Use absolute path for database to avoid file-not-found errors
DB = os.path.join(os.getcwd(), "claims.db")
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
      CREATE TABLE IF NOT EXISTS claims (
          id TEXT PRIMARY KEY,
          person TEXT,
          claim TEXT,
          source TEXT,
          url TEXT,
          truth_score TEXT,
          bias_rating TEXT,
          timestamp TEXT
      )
    ''')
    conn.commit()
    conn.close()

# -----------------------------
# SCRAPING & CLAIM EXTRACTION
# -----------------------------
def scrape_article(url):
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=". ")
        sentences = [s.strip() for s in text.split(".") if len(s.strip())>15]
        claims = [s for s in sentences if any(k in s.lower() for k in ["will","plan","promise","said","report"])]
        return text, claims
    except:
        return "", []

# -----------------------------
# GLOBAL CLAIM COMPARISON
# -----------------------------
def truth_score(claim, related_texts):
    if not related_texts:
        return "Partial"
    vectorizer = TfidfVectorizer().fit([claim] + related_texts)
    vectors = vectorizer.transform([claim] + related_texts)
    similarities = cosine_similarity(vectors[0:1], vectors[1:]).flatten()
    agree_percent = sum(sim>0.6 for sim in similarities)/len(similarities)
    if agree_percent > 0.8:
        return "True"
    elif agree_percent > 0.4:
        return "Partial"
    else:
        return "False"

# -----------------------------
# BIAS RATING
# -----------------------------
def bias_rating(article_text):
    blob = TextBlob(article_text)
    subjectivity = blob.sentiment.subjectivity
    if subjectivity < 0.3:
        return "Low"
    elif subjectivity < 0.6:
        return "Medium"
    else:
        return "High"

# -----------------------------
# SAVE TO DB
# -----------------------------
def save_claims(claims):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for claim in claims:
        c.execute('INSERT OR IGNORE INTO claims VALUES (?,?,?,?,?,?,?,?)', (
            str(uuid.uuid4()), claim["person"], claim["claim"],
            claim["source"], claim["url"], claim["truth_score"],
            claim["bias_rating"], str(datetime.now())
        ))
    conn.commit()
    conn.close()

# -----------------------------
# DASHBOARD
# -----------------------------
def display_dashboard():
    st.set_page_config(page_title="TruthLedger AI", layout="wide")
    st.markdown("""
    <style>
    body {background-color:#0a0a0a; color:#fff; font-family: 'Segoe UI', sans-serif;}
    .card {border:2px solid #0ff; border-radius:15px; padding:15px; margin:10px; background-color:#111;
           transition: transform 0.2s; box-shadow: 0 0 15px #0ff;}
    .card:hover {transform: scale(1.02); box-shadow: 0 0 25px #0ff;}
    .true {color:#0f0; font-weight:bold;}
    .partial {color:#ff0; font-weight:bold;}
    .false {color:#f00; font-weight:bold;}
    .low {color:#0f0;}
    .medium {color:#ff0;}
    .high {color:#f00;}
    a {color:#0ff;}
    </style>
    """, unsafe_allow_html=True)

    st.title("🛰️ TruthLedger AI — Futuristic News Analyzer")
    st_autorefresh(interval=60000, key="refresh")

    # Ensure DB table exists
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
      CREATE TABLE IF NOT EXISTS claims (
          id TEXT PRIMARY KEY,
          person TEXT,
          claim TEXT,
          source TEXT,
          url TEXT,
          truth_score TEXT,
          bias_rating TEXT,
          timestamp TEXT
      )
    ''')
    conn.commit()

    c.execute("SELECT person, claim, source, truth_score, bias_rating, timestamp FROM claims ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()

    for r in rows:
        person, claim, source, score, bias, timestamp = r
        st.markdown(
            f"""
            <div class='card'>
                <h3>{person}</h3>
                <p>{claim}</p>
                <p><b>Source:</b> <a href='{source}' target='_blank'>{source}</a></p>
                <p><b>Truth Score:</b> <span class='{score.lower()}'>{score}</span></p>
                <p><b>Bias Rating:</b> <span class='{bias.lower()}'>{bias}</span></p>
                <p><small>{timestamp}</small></p>
            </div>
            """,
            unsafe_allow_html=True
        )

# -----------------------------
# MAIN
# -----------------------------
init_db()

st.sidebar.title("🛠️ Control Panel")
st.sidebar.write("Automated zero-cost AI news analyzer")

# Preloaded global news URLs
default_urls = [
    "https://www.bbc.com/news/world-us-canada-67175669",
    "https://www.cnn.com/2025/09/22/technology/news-ai-update",
    "https://www.nytimes.com/2025/09/22/business/tech-startup-news.html"
]
urls_input = st.sidebar.text_area(
    "Enter news URLs (one per line)",
    value="\n".join(default_urls)
)

if st.sidebar.button("Scrape & Analyze"):
    urls = [u.strip() for u in urls_input.split("\n") if u.strip()]
    all_claims = []
    for url in urls:
        article_text, claims = scrape_article(url)
        if not article_text:
            continue
        bias = bias_rating(article_text)
        # Global comparison: reuse all other URLs for comparison
        related_texts = []
        for compare_url in urls:
            if compare_url == url:
                continue
            text,_ = scrape_article(compare_url)
            if text:
                related_texts.append(text)
        for claim in claims:
            all_claims.append({
                "person": "Unknown",
                "claim": claim,
                "source": url,
                "url": url,
                "truth_score": truth_score(claim, related_texts),
                "bias_rating": bias
            })
    save_claims(all_claims)
    st.sidebar.success(f"Analyzed {len(all_claims)} claims!")

display_dashboard()
