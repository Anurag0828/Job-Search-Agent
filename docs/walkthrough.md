# AI Job Search Agent — Complete Project Walkthrough

## How to Read This Document

This document explains **everything we've built**, **how each piece works**, and **how they all connect**. Read it top to bottom — it's written like a story, starting from the basics and building up.

---

# PART 1: The Big Picture

## What Are We Building?

Imagine you hire a **personal recruiter** who works 24/7:

1. First, you give them your **resume** 
2. Every morning, they **visit LinkedIn, Naukri, and Indeed** 
3. They **read every new job posting** (hundreds!) 
4. They **compare each job** to your resume 
5. They **throw away** anything that doesn't match 
6. They **send you ONE email** with the **5-10 best matches** 

That's exactly what this software does — except the "recruiter" is an AI agent running on your computer.

## The Complete Journey (What Happens When The System Runs)

```
YOU (one time)                    THE SYSTEM (every day, automatically)
─────────────                    ────────────────────────────────────

Upload resume.pdf                
       │                         
       ▼                         
   [Resume Agent]                
   Reads your PDF,               
   extracts skills,              
   saves profile                 
       │                         
       ▼                         
   Profile stored in DB ────────► [Scheduler fires at 8:00 AM]
                                          │
                                          ▼
                                  [Supervisor Agent]
                                  "Time to find jobs!"
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                     [LinkedIn]      [Naukri]         [Indeed]
                     Collector       Collector        Collector
                     Opens Chrome,   Opens Chrome,    Opens Chrome,
                     searches jobs,  searches jobs,   searches jobs,
                     extracts data   extracts data    extracts data
                          │               │               │
                          └───────────────┼───────────────┘
                                          ▼
                                   [Job Database]
                                   500 raw jobs stored
                                          │
                                          ▼
                                   [Matching Agent]
                                   Compares each job
                                   to YOUR profile
                                   Scores 0-100
                                          │
                                          ▼
                                   [Ranking Agent]
                                   Removes duplicates
                                   Sorts by score
                                   Keeps top 10
                                          │
                                          ▼
                                   [Memory Agent]
                                   "Already sent this yesterday?"
                                   Filters out repeats
                                          │
                                          ▼
                                   [Email Service]
                                   Sends ONE email with
                                   your best matches
                                          │
                                          ▼
                                      YOUR INBOX
                                   "Here are today's
                                    top 8 matches!"
```

---

# PART 2: Project Structure — What Each Folder Does

Here's every folder and file in the project. Think of this like a **building** — each floor has a specific purpose:

```
d:\Job search agent\
│
├── cli.py                  ← HEADLESS CLI: Run all commands from terminal (ingest, collect, match, email)
├── .env                    ← YOUR secrets (API keys, email password)
├── .env.example            ← Template showing what .env should look like
├── .gitignore              ← Tells Git to ignore secrets & temp files
├── README.md               ← Setup instructions
├── requirements.txt        ← List of all Python packages needed
├── launch_chrome.bat       ← Double-click to start Chrome with debug port
├── start_all.bat           ← Double-click to start headless background scheduler
│
├── config/                 ← FLOOR 1: Configuration
│   ├── __init__.py         ← Makes this folder a Python package
│   └── settings.py         ← Reads .env, provides settings to all files
│
├── database/               ← FLOOR 2: Data Storage
│   ├── __init__.py
│   ├── connection.py       ← How to connect to the database
│   └── models.py           ← What tables exist (users, jobs, recommendations)
│
├── schemas/                ← FLOOR 3: Data Shapes (Validation)
│   ├── __init__.py
│   ├── user_profile.py     ← Shape of a parsed resume
│   ├── job_posting.py      ← Shape of a job listing
│   └── recommendation.py   ← Shape of a final recommendation
│
├── services/               ← FLOOR 4: Shared Tools
│   ├── __init__.py
│   ├── llm_service.py      ← Talks to AI models (OpenAI, Gemini, Claude, NVIDIA NIM)
│   ├── embedding_service.py ← Local sentence-transformers vector embeddings
│   ├── vector_store.py     ← ChromaDB persistent vector database manager
│   ├── resume_rag_service.py ← RAG: Chunks resume & retrieves relevant evidence for jobs
│   ├── email_service.py    ← Sends emails via Gmail SMTP App Password
│   └── browser_service.py  ← Controls Chrome browser via Playwright CDP port 9222
│
├── agents/                 ← FLOOR 5: The Brains
│   ├── __init__.py
│   ├── resume_agent.py     ← Parses resume → structured profile with heuristic fallback
│   ├── matching_agent.py   ← Scores jobs using RAG evidence & offline vector similarity
│   ├── ranking_agent.py    ← Removes duplicates & sorts top recommendations
│   ├── memory_agent.py     ← Remembers past recommendations (avoid repeats)
│   ├── notification_agent.py ← Builds responsive HTML email digests
│   └── supervisor.py       ← Master orchestrator running the full pipeline
│
├── collectors/             ← FLOOR 6: Job Platform Scrapers
│   ├── __init__.py
│   ├── base_collector.py   ← Template that all collectors follow (Phase 3)
│   ├── linkedin_jobs.py    ← Scrapes LinkedIn Jobs (Phase 3)
│   ├── linkedin_posts.py   ← Scrapes LinkedIn hiring posts (Phase 3)
│   ├── naukri.py           ← Scrapes Naukri (Phase 3)
│   └── indeed.py           ← Scrapes Indeed (Phase 3)
│
├── api/                    ← FLOOR 7: Web Server (accepts your requests)
│   ├── __init__.py
│   ├── main.py             ← Starts the web server
│   └── routes/
│       ├── __init__.py
│       └── resume.py       ← Upload resume endpoint
│
├── scheduler/              ← FLOOR 8: Daily Timer
│   ├── __init__.py
│   └── daily_runner.py     ← Triggers the pipeline every morning (Phase 6)
│
├── data/                   ← Auto-created: SQLite database file lives here
├── uploads/                ← Auto-created: Your uploaded resume lives here
└── venv/                   ← Auto-created: Python virtual environment
```

---

# PART 3: How Each Piece Works (Deep Dive)

Let's trace the entire flow, file by file, in the order things actually happen.

---

## 3.1 Configuration — The Foundation

### [config/settings.py](file:///d:/Job search agent/config/settings.py)

**What it does:** Reads your `.env` file and makes all settings available to every other file.

**Why it exists:** Instead of every file doing `os.getenv("GEMINI_API_KEY")`, they all just do:
```python
from config.settings import settings
key = settings.GEMINI_API_KEY
```

**How it works:**
```
.env file (your secrets)
    │
    ▼
settings.py reads it using pydantic-settings
    │
    ▼
Creates a 'settings' object with typed fields
    │
    ▼
Every other file imports 'settings' and uses it
```

**Key concept — Single Source of Truth:** If you change your API key, you change it in ONE place (`.env`), and every file picks it up automatically.

---

## 3.2 Database — Where Data Lives

### [database/connection.py](file:///d:/Job search agent/database/connection.py)

**What it does:** Creates the connection to our SQLite database.

**Analogy:** Think of the database as a **filing cabinet**. `connection.py` is the **key** to open it.

```python
# Other files use it like this:
from database.connection import get_db

db = get_db()                    # Open the filing cabinet
jobs = db.query(JobPosting).all()  # Pull out the "Jobs" folder
db.close()                       # Close the cabinet
```

### [database/models.py](file:///d:/Job search agent/database/models.py)

**What it does:** Defines the structure of our 4 database tables.

**Analogy:** These are the **folders inside the filing cabinet** — each one has specific slots for specific information.

| Table (Folder) | What Goes In It | Example Row |
|---|---|---|
| `user_profiles` | Your parsed resume data | `name="Rahul", skills=["Python","React"], experience=5yr` |
| `job_postings` | Every job from every platform | `title="Backend Dev", company="Google", platform="linkedin"` |
| `recommendations` | Jobs we recommended to you | `job_id=42, score=92, rationale="Great Python match"` |
| `run_logs` | History of each daily run | `date="Jul 28", status="completed", jobs_found=347` |

**How tables connect:**
```
user_profiles ──────────────────────────────► matching_agent reads this
                                              to compare against jobs

job_postings ◄── collectors write here
             ──► matching_agent reads here
             ──► ranking_agent reads here

recommendations ◄── notification_agent writes here
                ──► memory_agent reads here (to avoid repeats)

run_logs ◄── supervisor writes here (tracking each daily run)
```

---

## 3.3 Schemas — Data Shapes (The Contracts)

### Why do we need schemas?

Imagine LinkedIn returns a job like this:
```python
{"job_title": "Engineer", "org": "Google"}
```

And Naukri returns it like this:
```python
{"designation": "Engineer", "company_name": "Google"}
```

If the Matching Agent expects `title` and `company`, both would break!

**Schemas are contracts** — they force everyone to speak the same language:

```
LinkedIn Collector → must produce → JobPosting(title=..., company=...)
Naukri Collector   → must produce → JobPosting(title=..., company=...)
Indeed Collector   → must produce → JobPosting(title=..., company=...)
                                     ↑
                                     SAME SHAPE — enforced by schema
```

### [schemas/user_profile.py](file:///d:/Job search agent/schemas/user_profile.py)

**Shape of a parsed resume:**
```python
UserProfile(
    full_name = "Rahul Sharma",
    skills = ["Python", "FastAPI", "React", "PostgreSQL"],
    experience_years = 5.0,
    seniority = "mid-senior",
    preferred_roles = ["Backend Engineer", "Full Stack Developer"],
    education = [{"degree": "B.Tech", "field": "CS", ...}],
    ...
)
```

### [schemas/job_posting.py](file:///d:/Job search agent/schemas/job_posting.py)

**Shape of a job listing (from any platform):**
```python
JobPosting(
    title = "Senior Backend Engineer",
    company = "Google",
    location = "Bangalore",
    description = "We're looking for a Python expert...",
    url = "https://linkedin.com/jobs/view/12345",
    platform = "linkedin_jobs",
    posted_date = "2 days ago",
)
```

### [schemas/recommendation.py](file:///d:/Job search agent/schemas/recommendation.py)

**Shape of a final recommendation (in the email):**
```python
Recommendation(
    title = "Senior Backend Engineer",
    company = "Google",
    match_score = 92.0,
    rationale = "Your 5 years of Python + FastAPI match perfectly...",
    missing_skills = ["Kubernetes", "gRPC"],
    job_url = "https://linkedin.com/jobs/view/12345",
)
```

---

## 3.4 LLM Service — The AI Brain

### [services/llm_service.py](file:///d:/Job search agent/services/llm_service.py)

**What it does:** Provides ONE simple way to talk to ANY AI model.

**Why a wrapper?** Here's the problem without it:

```python
# WITHOUT wrapper — if you switch from OpenAI to Gemini,
# you'd change EVERY file that calls an AI model:

# resume_agent.py
import openai
response = openai.chat.completions.create(model="gpt-4", messages=[...])

# matching_agent.py  
import openai
response = openai.chat.completions.create(model="gpt-4", messages=[...])

# ranking_agent.py
import openai
response = openai.chat.completions.create(model="gpt-4", messages=[...])

# Switching to Gemini? Change ALL 3 files! 😫
```

```python
# WITH wrapper — switch providers by changing ONE line in .env:

# resume_agent.py
from services.llm_service import get_llm
llm = get_llm()
response = llm.call("Parse this resume...")

# matching_agent.py
from services.llm_service import get_llm
llm = get_llm()
response = llm.call("Score this job...")

# Switching to Gemini? Change .env: LLM_PROVIDER=gemini ✅
# ALL files automatically use Gemini now!
```

**The two methods every agent uses:**

| Method | What It Returns | When To Use |
|---|---|---|
| `llm.call(prompt)` | Plain text string | When you want a free-form answer |
| `llm.call_json(prompt)` | Python dictionary | When you want structured data (skills list, scores, etc.) |

**How it works internally:**

```
Agent calls: llm.call("Parse this resume...")
     │
     ▼
llm_service checks: settings.LLM_PROVIDER = "gemini"
     │
     ▼
Routes to: _call_gemini(prompt)
     │
     ▼
Calls Google Gemini API
     │
     ▼
Returns response text to the agent
```

---

## 3.5 Resume Agent — Understanding Your Resume

### [agents/resume_agent.py](file:///d:/Job search agent/agents/resume_agent.py)

**What it does:** Takes your PDF/DOCX resume and converts it into a structured profile.

**Step-by-step flow:**

```
Step 1: You upload "resume.pdf"
            │
            ▼
Step 2: extract_text("resume.pdf")
        Opens the PDF, reads every page,
        combines all text into one string:
        "Rahul Sharma | Python Developer | 5 years experience..."
            │
            ▼
Step 3: analyze_with_llm(raw_text)
        Sends the text to Gemini with a prompt:
        "Extract skills, experience, education from this resume..."
            │
            ▼
Step 4: Gemini returns JSON:
        {
          "full_name": "Rahul Sharma",
          "skills": ["Python", "FastAPI", "React"],
          "experience_years": 5,
          "seniority": "mid-senior",
          ...
        }
            │
            ▼
Step 5: Validate against UserProfile schema
        (catches errors if Gemini returns bad data)
            │
            ▼
Step 6: Save to database (user_profiles table)
            │
            ▼
Step 7: Return the UserProfile object
```

**The prompt we send to the LLM (simplified):**

> "You are an expert resume parser. Here is a resume:
> [raw text]
> Extract: full_name, skills, experience_years, seniority, preferred_roles...
> Return as JSON."

**Why the LLM is good at this:** Traditional resume parsers use rigid rules ("find text after 'Skills:'"). LLMs understand context — they can find skills even if the resume says "Technologies used" or "Technical toolkit" instead of "Skills."

---

## 3.6 API Server — How You Interact With the System

### [api/main.py](file:///d:/Job search agent/api/main.py)

**What it does:** Runs a web server on your computer (`http://localhost:8000`).

**Think of it as a receptionist:** You make requests → it routes them to the right agent → returns the result.

### [api/routes/resume.py](file:///d:/Job search agent/api/routes/resume.py)

**Endpoints (things you can ask the server to do):**

| Endpoint | Method | What It Does |
|---|---|---|
| `POST /api/resume/upload` | Upload | Receives your resume file, parses it |
| `GET /api/resume/profile` | View | Shows your current parsed profile |
| `GET /api/health` | Check | Confirms the server is running |

**Upload flow:**
```
You: POST /api/resume/upload with file=resume.pdf
  │
  ▼
API receives the file
  │
  ▼
Saves to d:\Job search agent\uploads\resume.pdf
  │
  ▼
Calls ResumeAgent().parse_resume("uploads/resume.pdf")
  │
  ▼
Returns: {"status": "success", "profile": {...}}
```

---

# PART 4: What's Coming Next (Phases 3-7)

Here's how the remaining pieces will connect to what we've already built:

## Phase 3: Platform Collectors (How the agent searches for jobs)

```
browser_service.py — Connects Playwright to YOUR Chrome
       │
       ▼
base_collector.py — Defines the "contract" every collector follows:
       │             search() → extract() → collect()
       │
       ├── linkedin_jobs.py  — Implements the contract for LinkedIn
       │     1. Opens new tab in your Chrome
       │     2. Goes to linkedin.com/jobs
       │     3. Types your search query ("Python Developer")
       │     4. Sets filters (location, date posted)
       │     5. Scrapes each job listing
       │     6. Returns list of JobPosting objects
       │
       ├── naukri.py — Same pattern for Naukri
       │
       └── indeed.py — Same pattern for Indeed
```

**Chrome session reuse — how it works:**
```
Normal situation:
  You: logged into LinkedIn in Chrome
  Agent: has NO access to your Chrome → would need to log in

With debug port (launch_chrome.bat):
  You: launch Chrome with --remote-debugging-port=9222
  Agent: connects to your RUNNING Chrome via port 9222
  Agent: opens a new tab → LinkedIn sees it as YOU
  Agent: scrapes jobs → closes the tab
  Your login: untouched, agent never sees your password
```

## Phase 4: Matching, Ranking & RAG Semantic Retrieval

Instead of comparing jobs against a single short summary of your resume, our agent uses **RAG (Retrieval-Augmented Generation)** for maximum precision:

### 1. Resume Ingestion (Semantic Chunking in ChromaDB)
When you run `python cli.py ingest --file resume.pdf`, your resume is automatically partitioned into **semantic chunks** (Summary, Technical Skills, Work Experience items, Projects, Education). Each section is converted into a **384-dimensional vector** using our local `sentence-transformers` model and stored in ChromaDB (`user_resume_chunks` collection).

### 2. RAG Job Matching Flow
```
  Job Posting comes in: "Looking for LangChain & pgvector engineer..."
          │
          ▼
  [ResumeRagService.retrieve_relevant_chunks()]
  Queries ChromaDB vector store for top 3 matching sections of YOUR resume:
          │
          ├─► Retrieved Chunk 1: [TECHNICAL SKILLS] Python, LangChain, LangGraph, RAG, pgvector
          ├─► Retrieved Chunk 2: [PROJECTS] Scaler AI Persona (Autonomous RAG Voice & Chat Agent)
          └─► Retrieved Chunk 3: [EXPERIENCE] AI Engineer building LangChain workflows
          │
          ▼
  [MatchingAgent — Offline Fallback or LLM Analysis]
  Evaluates exact evidence against the job description:
          │
          ├─► If offline (no API key): Computes 0-100 score directly from RAG cosine similarity!
          └─► If LLM configured (NVIDIA NIM / Gemini): Sends exact RAG evidence to AI model
              to generate a deep rationale and identify any skill gaps.
```

```
ranking_agent.py:
  
  50 scored jobs come in
       │
       ▼
  Deduplication: "This Google job is on LinkedIn AND Naukri"
                  → Keep one, discard the other
       │
       ▼
  Sort by score: 95, 92, 88, 85, 78, 72, 65, 55, 40, 30...
       │
       ▼
  Cutoff: Only keep score ≥ 65
       │
       ▼
  Top 10: Take the best 10 for today's email
```

## Phase 5: Email (The final output)

```
notification_agent.py:
  
  Takes the top 10 recommendations
       │
       ▼
  Renders HTML email using templates/email_digest.html
       │
       ▼
  Each job becomes a "card" in the email:
  ┌─────────────────────────────────────────┐
  │ 🏢 Google • Senior Backend Engineer     │
  │ 📍 Bangalore • Match: 92%              │
  │                                         │
  │ WHY: Your Python + FastAPI experience   │
  │ directly matches their requirements...  │
  │                                         │
  │ GAPS: Kubernetes, gRPC                  │
  │                                         │
  │ [View Job →]                            │
  └─────────────────────────────────────────┘
       │
       ▼
  email_service.py sends via Gmail SMTP
       │
       ▼
  YOUR INBOX 📧
```

## Phase 6: Orchestration (Wiring it all together)

```
supervisor.py (LangGraph):
  
  Every morning at 8:00 AM (APScheduler triggers):
  
  START
    │
    ├─ Step 1: Load user profile from database
    │
    ├─ Step 2: Run all collectors IN PARALLEL
    │          (LinkedIn, Naukri, Indeed — at the same time)
    │
    ├─ Step 3: Save collected jobs to database
    │
    ├─ Step 4: Run matching (score each job)
    │
    ├─ Step 5: Run ranking (sort + filter)
    │
    ├─ Step 6: Check memory (remove already-recommended)
    │
    ├─ Step 7: Send email
    │
    └─ Step 8: Log the run results
  END
  
  If LinkedIn breaks? → Log error, skip it, continue with Naukri + Indeed
  If email fails?     → Log error, save recommendations for tomorrow
```

---

# PART 5: How Everything Connects — The Connection Map

```
┌──────────────────────────────────────────────────────────────────┐
│                        .env (configuration)                      │
│   API keys, email credentials, search preferences, toggles      │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
                    config/settings.py
                    (reads .env once, shares with everyone)
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    services/          database/         api/main.py
    llm_service.py     connection.py     (web server)
    (AI brain)         models.py              │
          │            (data storage)         │
          │                │                  ▼
          ▼                ▼           api/routes/resume.py
    agents/            schemas/        (handles your requests)
    resume_agent.py    user_profile.py        │
    matching_agent.py  job_posting.py         │
    ranking_agent.py   recommendation.py      │
          │                │                  │
          │                │                  │
          ▼                ▼                  │
    collectors/        All agents use         │
    linkedin_jobs.py   schemas to validate    │
    naukri.py          their input/output     │
    indeed.py               │                 │
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                            ▼
                    supervisor.py
                    (orchestrates the daily pipeline)
                            │
                            ▼
                    scheduler/daily_runner.py
                    (triggers supervisor every morning)
```

---

# PART 6: Key Design Principles (Why We Built It This Way)

## Principle 1: Separation of Concerns
Each file does **ONE thing**. The Resume Agent doesn't know how to send emails. The Email Service doesn't know how to parse resumes. This makes bugs easy to find and fix.

## Principle 2: Loose Coupling
Agents don't call each other directly. They communicate through the **database** and **schemas**. If the LinkedIn collector breaks, the Matching Agent doesn't care — it just processes whatever jobs ARE in the database.

## Principle 3: Single Source of Truth
Configuration lives in ONE place (`.env` → `settings.py`). Database schemas live in ONE place (`schemas/`). No duplicated definitions.

## Principle 4: Fail Gracefully
If one platform's collector fails, the rest still run. If matching fails for one job, it skips that job. The system never crashes completely — it degrades gracefully.

## Principle 5: Pluggability
Want to add Glassdoor? Write ONE new file (`collectors/glassdoor.py`) following the same interface. Nothing else changes. Want to switch from Gemini to OpenAI? Change ONE line in `.env`.

---

# PART 7: What We've Built So Far vs. What's Left

| Component | Status | Files |
|---|---|---|
| Configuration | ✅ Built | `.env`, `config/settings.py` |
| Database | ✅ Built | `database/connection.py`, `database/models.py` |
| Schemas | ✅ Built | `schemas/user_profile.py`, `schemas/job_posting.py`, `schemas/recommendation.py` |
| LLM Service | ✅ Built | `services/llm_service.py` |
| Resume Agent | ✅ Built | `agents/resume_agent.py` |
| API Server | ✅ Built | `api/main.py`, `api/routes/resume.py`, `api/routes/jobs.py` |
| Browser Service | ✅ Built | `services/browser_service.py` |
| Collectors | ✅ Built | `collectors/base_collector.py`, `collectors/linkedin_jobs.py`, `collectors/naukri.py` |
| Matching Agent | ✅ Built | `agents/matching_agent.py`, `services/embedding_service.py`, `services/vector_store.py` |
| Ranking Agent | ✅ Built | `agents/ranking_agent.py` |
| Memory Agent | ✅ Built | `agents/memory_agent.py` |
| Email Service | ✅ Built | `services/email_service.py` |
| Notification Agent | ✅ Built | `agents/notification_agent.py` |
| Supervisor | ✅ Built | `agents/supervisor.py` |
| Scheduler | ✅ Built | `scheduler/daily_runner.py` |
| Dashboard | ✅ Built | `dashboard/app.py`, `start_all.bat` |

**The AI Job Search Agent is 100% complete!** You now have a full, end-to-end autonomous recruiter with local vector embeddings, two-layer LLM matching, automated Gmail notifications, and a rich Streamlit web dashboard. Double-click `start_all.bat` to launch everything!
