import os, sqlite3, uuid, requests, time
from newspaper import Article
from datetime import datetime
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# -----------------------------
# SETUP
# -----------------------------
DB = "claims.db"
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
          timestamp TEXT
      )
    ''')
    conn.commit()
    conn.close()

# -----------------------------
# SCRAPING & CLAIM EXTRACTION
# -----------------------------
def scrape_news(url_list):
    claims_extracted = []
    for url in url_list:
        try:
            article = Article(url)
            article.download()
            article.parse()
            text = article.text
            # Simple AI-free claim extraction for MVP
            for line in text.split("."):
                line = line.strip()
                if any(word in line.lower() for word in ["will", "plan", "promise"]):
                    claims_extracted.append({
                        "person": "Unknown",
                        "claim": line,
                        "source": url,
                        "url": url
                    })
        except:
            continue
    return claims_extracted

# -----------------------------
# VERIFICATION (AI MOCK)
# -----------------------------
def verify_claim(claim_text):
    keywords_false = ["never", "impossible", "fail"]
    keywords_partial = ["maybe", "could", "possibly"]
    if any(word in claim_text.lower() for word in keywords_false):
        return "False"
    elif any(word in claim_text.lower() for word in keywords_partial):
        return "Partial"
    return "True"

# -----------------------------
# SAVE TO DB
# -----------------------------
def save_claims(claims):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for claim in claims:
        c.execute('INSERT OR IGNORE INTO claims VALUES (?,?,?,?,?,?,?)', (
            str(uuid.uuid4()), claim["person"], claim["claim"],
            claim["source"], claim["url"], verify_claim(claim["claim"]),
            str(datetime.now())
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
    a {color:#0ff;}
    </style>
    """, unsafe_allow_html=True)

    st.title("🛰️ TruthLedger AI — Futuristic Claims Dashboard")
    st_autorefresh(interval=60000, key="refresh")  # auto-refresh every 60s

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT person, claim, source, truth_score, timestamp FROM claims ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()

    for r in rows:
        person, claim, source, score, timestamp = r
        score_class = score.lower()
        st.markdown(f"""
        <div class='card'>
        <h3>{person}</h3>
        <p>{claim}</p>
        <p><b>Source:</b> <a href='{source}' target='_blank'>{source}</a></p>
        <p><b>Truth Score:</b> <span class='{score_class}'>{score}</span></p>
        <p><small>{timestamp}</small></p>
        </div>
        """, unsafe_allow_html=True)

# -----------------------------
# MAIN
# -----------------------------
init_db()

st.sidebar.title("🛠️ Control Panel")
st.sidebar.write("Automated zero-cost AI news receipts site")
urls_input = st.sidebar.text_area("Enter news URLs (one per line)")

if st.sidebar.button("Scrape & Update Claims"):
    urls = [u.strip() for u in urls_input.split("\n") if u.strip()]
    new_claims = scrape_news(urls)
    save_claims(new_claims)
    st.sidebar.success(f"Added {len(new_claims)} new claims!")

display_dashboard()
