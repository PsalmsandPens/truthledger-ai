import os, sqlite3, uuid, requests
from datetime import datetime
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from bs4 import BeautifulSoup

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
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(separator=". ")
            for line in text.split("."):
                line = line.strip()
                if any(word in line.lower() for word in ["will", "plan", "promise"]):
                    claim_dict = {
                        "person": "Unknown",
                        "claim": line,
                        "source": url,
                        "url": url
                    }
                    claims_extracted.append(claim_dict)
        except:
            continue
    return claims_extracted
