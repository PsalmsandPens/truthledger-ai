import os, sqlite3, uuid
from datetime import datetime
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from textblob import TextBlob
import nltk

nltk.download('punkt')

# -----------------------------
# SETUP
# -----------------------------
DB = os.path.join(os.getcwd(), "claims.db")
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='claims'")
    if not c.fetchone():
        c.execute('''
          CREATE TABLE claims (
              id TEXT PRIMARY KEY,
              title TEXT,
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
BIAS_WORDS = [
    "outrageous", "shocking", "exclusive", "allegedly", "claims",
    "horrific", "devastating", "incredible", "disaster", "miracle"
]

def scrape_article(url):
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text().strip() if title_tag else "Untitled Article"
        
        # Extract paragraphs
        paragraphs = soup.find_all('p')
        text = " ".join(p.get_text() for p in paragraphs if len(p.get_text())>15)
        
        # Extract claims
        sentences = [s.strip() for s in text.split(".") if len(s.strip())>15]
        claims = [s for s in sentences if any(k in s.lower() for k in ["will","plan","promise","said","report"])]
        
        return title, text, claims
    except:
        return "Untitled Article", "", []

# -----------------------------
# TRUTH SCORE
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
    if not article_text or len(article_text.strip()) < 50:
        return "Medium"
    blob = TextBlob(article_text)
    subjectivity = blob.sentiment.subjectivity
    
    # Boost based on bias words
    words = article_text.lower().split()
    bias_word_count = sum(word in BIAS_WORDS for word in words)
    bias_ratio = bias_word_count / max(1, len(words))
    adjusted_subjectivity = subjectivity + bias_ratio
    
    if adjusted_subjectivity < 0.25:
        return "Low"
    elif adjusted_subjectivity < 0.5:
        return "Medium"
    else:
        return "High"

# -----------------------------
# SAVE CLAIMS TO DB
# -----------------------------
def save_claims(claims):
    if not claims:
        return
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for claim in claims:
        if not claim.get("claim") or len(claim.get("claim").strip())==0:
            continue
        try:
            c.execute('INSERT OR IGNORE INTO claims VALUES (?,?,?,?,?,?,?,?)', (
                str(uuid.uuid4()),
                claim.get("title", "Untitled Article"),   # Title stored here
                claim["claim"].strip(),
                claim.get("source",""),
                claim.get("url",""),
                claim.get("truth_score","Partial"),
                claim.get("bias_rating","Medium"),       # Bias rating stored correctly
                str(datetime.now())
            ))
        except Exception as e:
            st.warning(f"Skipping claim due to DB error: {e}")
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

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    try:
        c.execute("SELECT title, claim, source, truth_score, bias_rating, timestamp FROM claims ORDER BY timestamp DESC")
        rows = c.fetchall()
    except:
        rows = []
    conn.close()

    if not rows:
        st.info("No claims found yet. Click 'Scrape & Analyze' to add news claims.")
        return

    for r in rows:
        title, claim, source, truth, bias, timestamp = r
        score_str = str(truth) if truth else "Partial"
        bias_str = str(bias) if bias else "Medium"
        st.markdown(
            f"""
            <div class='card'>
                <h3>{title}</h3>
                <p>{claim}</p>
                <p><b>Source:</b> <a href='{source}' target='_blank'>{source}</a></p>
                <p><b>Truth Score:</b> <span class='{score_str.lower()}'>{score_str}</span></p>
                <p><b>Bias Rating:</b> <span class='{bias_str.lower()}'>{bias_str}</span></p>
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
        title, article_text, claims = scrape_article(url)
        if not article_text or not claims:
            continue
        bias = bias_rating(article_text)
        related_texts = []
        for compare_url in urls:
            if compare_url == url:
                continue
            _, text,_ = scrape_article(compare_url)
            if text:
                related_texts.append(text)
        for claim in claims:
            claim_data = {
                "title": title,          # Title now stored correctly
                "claim": claim.strip(),
                "source": url,
                "url": url,
                "truth_score": truth_score(claim, related_texts),
                "bias_rating": bias       # Bias rating stored correctly
            }
            all_claims.append(claim_data)
    if all_claims:
        save_claims(all_claims)
        st.sidebar.success(f"Analyzed {len(all_claims)} claims!")
    else:
        st.sidebar.warning("No claims were found for the provided URLs.")

display_dashboard()
