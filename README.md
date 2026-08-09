# 🤖 AI Job Search Agent (RAG + Headless CLI Edition)

Your autonomous, 24/7 personal AI recruiter built in Python. Designed for **zero-UI background operation**, it uses **RAG (Retrieval-Augmented Generation)** with ChromaDB vector embeddings to semantically match job postings against specific achievements and projects in your resume, delivering curated opportunities directly to your email inbox.

---

## 🌟 Key Features

1. **Semantic Resume RAG (ChromaDB + sentence-transformers)**: Instead of summarizing your resume into one short paragraph, the system partitions your resume into semantic sections (Summary, Technical Skills, Work Experience, Projects, Education). When analyzing a job posting, it queries ChromaDB for the top 3 most relevant sections of your resume as proof of qualification!
2. **Two-Layer Matching Strategy**:
   - **Layer 1 (Vector Filter)**: Scans 500+ collected jobs offline in milliseconds using local embeddings ($0 API cost).
   - **Layer 2 (LLM Deep Analysis)**: Sends top candidates + retrieved RAG evidence to an AI model (**NVIDIA NIM**, **Google Gemini**, **OpenAI**, or **Claude**) for a 0-100 score and rationale.
   - **Offline Fallback**: If no LLM API key is configured, the pipeline automatically computes 0-100 scores directly from local RAG cosine similarity without failing or crashing!
3. **Session Reusing Scrapers (Playwright CDP)**: Connects to your running Chrome browser (`port 9222`) so it searches LinkedIn and Naukri using your active login session—no credentials or passwords required!
4. **Smart Vector Memory**: Tracks recommended jobs across a 30-day window so you never receive duplicate emails.
5. **Headless Command Line Interface (`cli.py`)**: Clean terminal commands to manage everything without opening web dashboards.

---

## 🚀 Quick Start Guide

### Step 1: Install Dependencies
```powershell
cd "d:\Job search agent"
.\venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### Step 2: Configure Secrets & Keywords
Copy `.env.example` to `.env` and edit your preferences:
```ini
# Choose LLM Provider: "gemini", "nvidia", "openai", or "claude"
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_api_key_here

# For NVIDIA NIM:
# LLM_PROVIDER=nvidia
# NVIDIA_API_KEY=nvapi-...
# NVIDIA_MODEL=meta/llama-3.1-70b-instruct

# Set your email for daily digests (requires Gmail App Password):
EMAIL_SENDER=your.email@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECIPIENT=your.email@gmail.com

# Target job keywords & locations:
SEARCH_QUERIES=AI Engineer,LLM Engineer,GenAI Engineer,RAG Engineer,Python AI Developer
SEARCH_LOCATIONS=Dehradun,Bangalore,Remote,India
```

### Step 3: Ingest Your Resume into RAG Vector DB
Run our CLI command to chunk your PDF and store embeddings in ChromaDB:
```powershell
.\venv\Scripts\python.exe cli.py ingest --file "Anurag_Sajwan_Resume_Updated_July2026.pdf"
```

### Step 4: Launch Chrome for Scraping
Double-click **`launch_chrome.bat`** (or run `chrome.exe --remote-debugging-port=9222`). Make sure you are logged into LinkedIn and Naukri in this Chrome window.

### Step 5: Run Your Job Hunt!
Use our clean CLI commands to control the agent:

| Command | What It Does |
|---|---|
| `python cli.py status` | Shows counts of resume chunks, stored jobs, and recommendations |
| `python cli.py collect` | Scrapes new job listings from LinkedIn and Naukri |
| `python cli.py match` | Evaluates jobs against your resume chunks using RAG |
| `python cli.py email` | Sends the HTML email digest to your inbox |
| `python cli.py run-all` | Runs the full autonomous pipeline from start to finish |

---

## 💡 Automated Daily Operation

Want the agent to run automatically every morning at 8:00 AM? Just double-click **`start_all.bat`**. It launches the background scheduler (`scheduler/daily_runner.py`) which runs the full pipeline while you sip your morning coffee!
