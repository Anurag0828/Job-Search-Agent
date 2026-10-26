# AI Job Search Agent — Interview Walkthrough Guide

> **Purpose:** This guide is your cheat sheet when presenting this project to interviewers. It gives you the exact script to say, the exact files and functions to open on your screen, key technical highlights, and answers to follow-up questions.

---

## Table of Contents

1. [The 2-Minute Elevator Pitch (Memorize This)](#1-the-2-minute-elevator-pitch)
2. [Quick Reference Map (File & Function Cheat Sheet)](#2-quick-reference-map)
3. [Step-by-Step Code Walkthrough](#3-step-by-step-code-walkthrough)
   - [Step 0: The Orchestrator & Entry Point](#step-0-the-orchestrator--entry-point)
   - [Step 1: Session Authentication & Anti-Bot Browsing](#step-1-session-authentication--anti-bot-browsing)
   - [Step 2: Platform Scraping & Polymorphic Collectors](#step-2-platform-scraping--polymorphic-collectors)
   - [Step 3: Pydantic Data Contracts & SQLite Persistence](#step-3-pydantic-data-contracts--sqlite-persistence)
   - [Step 4: Resume Ingestion & RAG Semantic Chunking](#step-4-resume-ingestion--rag-semantic-chunking)
   - [Step 5: The Two-Tier Matching Engine (Core AI)](#step-5-the-two-tier-matching-engine-core-ai)
   - [Step 6: Unified LLM Interface with Rate Limiter](#step-6-unified-llm-interface-with-rate-limiter)
   - [Step 7: Ranking, Fuzzy Deduplication & Score Cutoff](#step-7-ranking-fuzzy-deduplication--score-cutoff)
   - [Step 8: Memory Agent & 30-Day Lookback Filter](#step-8-memory-agent--30-day-lookback-filter)
   - [Step 9: Notification Digest & SMTP Delivery](#step-9-notification-digest--smtp-delivery)
4. [Tough Interview Questions & Winning Answers](#4-tough-interview-questions--winning-answers)

---

## 1. The 2-Minute Elevator Pitch

> *"I built an autonomous AI Job Search Agent that automates the entire job hunt lifecycle. Every 4 hours, it scrapes live openings from LinkedIn, Naukri, and Indeed using Playwright, validates data through Pydantic contracts, and evaluates them against my resume using a **Two-Tier Matching Engine**.*
>
> *Tier 1 uses local sentence embeddings and ChromaDB vector search to instantly filter hundreds of jobs down to the top 30 candidates for zero API cost. Tier 2 applies RAG to retrieve the exact relevant sections of my resume and feeds them into an LLM (NVIDIA NIM / Llama 3.1 / DeepSeek) to generate deep match scores, rationales, and skill gaps.*
>
> *Finally, a Ranking Agent deduplicates listings via fuzzy matching, a Memory Agent ensures I never receive repeat recommendations within 30 days, and a Notification Agent sends a styled HTML email digest directly to my inbox."*

---

## 2. Quick Reference Map

| Pipeline Step | Key File | Key Class / Function | What to Show |
|---|---|---|---|
| **0. Pipeline Trigger** | [`scheduler/continuous_runner.py`](file:///d:/Job%20search%20agent/scheduler/continuous_runner.py) | `start_scheduler()`, `run_pipeline()` | APScheduler 4-hour cron loop |
| **0. Supervisor Brain** | [`agents/supervisor.py`](file:///d:/Job%20search%20agent/agents/supervisor.py) | `SupervisorAgent.run_pipeline()` | 8-step fault-tolerant pipeline |
| **1. Browser & Auth** | [`services/browser_service.py`](file:///d:/Job%20search%20agent/services/browser_service.py) | `connect()`, `interactive_login()` | `auth.json` cookies & headless Chromium |
| **2. Scrapers** | [`collectors/base_collector.py`](file:///d:/Job%20search%20agent/collectors/base_collector.py)<br>[`collectors/linkedin_jobs.py`](file:///d:/Job%20search%20agent/collectors/linkedin_jobs.py) | `BaseCollector.collect()`<br>`LinkedInJobsCollector.extract_listings()` | Polymorphic scrapers, click-to-load details |
| **3. Schema & DB** | [`schemas/job_posting.py`](file:///d:/Job%20search%20agent/schemas/job_posting.py)<br>[`database/models.py`](file:///d:/Job%20search%20agent/database/models.py) | `JobPosting`<br>`JobPostingModel`, `UserProfileModel` | Pydantic validation & SQLAlchemy tables |
| **4. Resume RAG** | [`services/resume_rag_service.py`](file:///d:/Job%20search%20agent/services/resume_rag_service.py) | `_semantic_chunking()`, `retrieve_relevant_chunks()` | Section splitting & vector storage in ChromaDB |
| **5. Tier 1 Matching** | [`agents/matching_agent.py`](file:///d:/Job%20search%20agent/agents/matching_agent.py)<br>[`services/vector_store.py`](file:///d:/Job%20search%20agent/services/vector_store.py) | `_vector_match()`<br>`VectorStore.find_similar()` | ChromaDB cosine similarity top-30 cutoff |
| **5. Tier 2 Matching** | [`agents/matching_agent.py`](file:///d:/Job%20search%20agent/agents/matching_agent.py) | `_score_single_job()` | RAG evidence injection & Hallucination clamp |
| **6. LLM Engine** | [`services/llm_service.py`](file:///d:/Job%20search%20agent/services/llm_service.py) | `LLMService.call_json()`, `RateLimiter` | Provider-agnostic API + exponential backoff |
| **7. Ranking & Dedup** | [`agents/ranking_agent.py`](file:///d:/Job%20search%20agent/agents/ranking_agent.py) | `rank_jobs()`, `_fuzzy_dedup()` | `SequenceMatcher` cross-platform dedup + threshold |
| **8. Memory Loop** | [`agents/memory_agent.py`](file:///d:/Job%20search%20agent/agents/memory_agent.py) | `filter_seen()`, `record_recommendations()` | 30-day lookback SQL check & user feedback |
| **9. HTML Email** | [`agents/notification_agent.py`](file:///d:/Job%20search%20agent/agents/notification_agent.py)<br>[`services/email_service.py`](file:///d:/Job%20search%20agent/services/email_service.py) | `send_digest()`<br>`EmailService.send()` | Responsive inline CSS template + Gmail SMTP |

---

## 3. Step-by-Step Code Walkthrough

---

### Step 0: The Orchestrator & Entry Point

#### 📂 Open File: [`agents/supervisor.py`](file:///d:/Job%20search%20agent/agents/supervisor.py)
#### 🔍 Function: `run_pipeline()` (Line 78)

```python
def run_pipeline(self) -> dict:
    # Step 1: Check user profile exists
    # Step 2: Run collectors (LinkedIn, Naukri, Indeed)
    # Step 3: Save new jobs to DB
    # Step 4: Run Two-Tier Matching Agent
    # Step 5: Run Ranking Agent (dedup + score cutoff)
    # Step 6: Run Memory Agent (filter already seen)
    # Step 7: Send HTML Email digest
    # Step 8: Update run_logs in DB
```

#### 🗣️ What to Say to the Interviewer:
> *"Here is `supervisor.py`, which acts as the stateful orchestrator. I designed it with comprehensive fault tolerance: every individual step is wrapped in try/except blocks. If LinkedIn scraping fails or encounters an unexpected DOM change, the pipeline records the error in the `run_logs` table and proceeds with Naukri and Indeed without crashing."*

---

### Step 1: Session Authentication & Anti-Bot Browsing

#### 📂 Open File: [`services/browser_service.py`](file:///d:/Job%20search%20agent/services/browser_service.py)
#### 🔍 Functions: `interactive_login()` (Line 117) & `connect()` (Line 59)

#### 🗣️ What to Say to the Interviewer:
> *"To avoid dealing with captchas on every run, I built an interactive login session manager. You run `python cli.py login` once: Playwright opens a visible browser window where you log in. Playwright exports your authenticated browser state (cookies and localStorage) into `auth.json`. 
>
> During production runs, `connect()` launches Playwright Chromium with `--disable-blink-features=AutomationControlled` and injects `auth.json`. This allows the agent to browse job boards as an authenticated user."*

---

### Step 2: Platform Scraping & Polymorphic Collectors

#### 📂 Open File: [`collectors/base_collector.py`](file:///d:/Job%20search%20agent/collectors/base_collector.py)
#### 🔍 Functions: `collect()` (Line 63) & `collect_multiple_queries()` (Line 128)

#### 📂 Open File: [`collectors/linkedin_jobs.py`](file:///d:/Job%20search%20agent/collectors/linkedin_jobs.py)
#### 🔍 Function: `extract_listings()` (Line 113)

#### 🗣️ What to Say to the Interviewer:
> *"I implemented the Strategy / Template Method pattern using an abstract base class `BaseCollector`. All platform scrapers—LinkedIn, Naukri, Indeed—inherit from it and must implement `search()` and `extract_listings()`.
>
> For LinkedIn, we load the search results, scroll the left rail to trigger lazy loading of cards, and click each card individually so the full job description renders on the right side for complete text extraction."*

---

### Step 3: Pydantic Data Contracts & SQLite Persistence

#### 📂 Open File: [`schemas/job_posting.py`](file:///d:/Job%20search%20agent/schemas/job_posting.py) & [`database/models.py`](file:///d:/Job%20search%20agent/database/models.py)
#### 🔍 Classes: `JobPosting` and `JobPostingModel`

#### 🗣️ What to Say to the Interviewer:
> *"To prevent schema drift across scrapers, every collector outputs a strict Pydantic model (`JobPosting`). This guarantees that regardless of platform-specific DOM variations, all jobs have normalized fields: `title`, `company`, `location`, `description`, and `url`.
>
> In `supervisor._save_jobs()`, jobs are deduplicated against the database by URL before insertion into the `job_postings` table via SQLAlchemy."*

---

### Step 4: Resume Ingestion & RAG Semantic Chunking

#### 📂 Open File: [`services/resume_rag_service.py`](file:///d:/Job%20search%20agent/services/resume_rag_service.py)
#### 🔍 Functions: `_semantic_chunking()` (Line 131) & `retrieve_relevant_chunks()` (Line 223)

#### 🗣️ What to Say to the Interviewer:
> *"Instead of passing an entire resume into the LLM context window, I built a RAG pipeline. When a resume PDF is uploaded, `_semantic_chunking()` parses section headers—Summary, Technical Skills, Experience, Projects, and Education—and converts them into separate semantic chunks.
>
> Each chunk is embedded using sentence-transformers and stored in ChromaDB in the `user_resume_chunks` collection. When evaluating a job, `retrieve_relevant_chunks()` performs a vector query with the job description to retrieve the top 3 most relevant resume sections as grounded evidence."*

---

### Step 5: The Two-Tier Matching Engine (Core AI)

#### 📂 Open File: [`agents/matching_agent.py`](file:///d:/Job%20search%20agent/agents/matching_agent.py)
#### 🔍 Functions: `_vector_match()` (Line 138) & `_score_single_job()` (Line 229)

#### 🗣️ What to Say to the Interviewer:
> *"This is the core architectural innovation of the project. Passing 300-500 raw jobs to an LLM would cause high latency and API rate-limit errors. I solved this with a two-tier approach:
>
> 1. **Tier 1 (Vector Pre-Filter):** `_vector_match()` embeds all job descriptions into ChromaDB using a local `all-MiniLM-L6-v2` model. We perform a cosine similarity search against the user profile to narrow the list down to the **top 30 candidate jobs**. This takes 2 seconds and costs $0.
>
> 2. **Tier 2 (LLM Deep Scoring):** For each of the top 30 candidates, `_score_single_job()` retrieves the 3 most relevant resume chunks from ChromaDB, constructs a structured prompt, and queries the LLM for JSON containing: `match_score` (0-100), `rationale`, and `missing_skills`.*
>
> **Safety Guardrails:**
> - **Prompt Injection Defense (Line 239):** Regex sanitizes job descriptions to prevent adversarial prompt injection.
> - **Hallucination Clamp (Line 306):** If the LLM score is >35 points higher than the offline RAG vector similarity, the two scores are averaged to prevent hallucinated fit.*

---

### Step 6: Unified LLM Interface with Rate Limiter

#### 📂 Open File: [`services/llm_service.py`](file:///d:/Job%20search%20agent/services/llm_service.py)
#### 🔍 Classes: `RateLimiter` (Line 41) & `LLMService` (Line 57)

#### 🗣️ What to Say to the Interviewer:
> *"I built a unified, provider-agnostic LLM interface. By changing one variable in `.env` (`LLM_PROVIDER`), the system switches between NVIDIA NIM, OpenAI, Gemini, and Claude without altering any agent code.
>
> It includes a token-bucket `RateLimiter` configured to 35 RPM to stay safely under free-tier API thresholds, plus exponential backoff retry logic for 429 rate-limit responses."*

---

### Step 7: Ranking, Fuzzy Deduplication & Score Cutoff

#### 📂 Open File: [`agents/ranking_agent.py`](file:///d:/Job%20search%20agent/agents/ranking_agent.py)
#### 🔍 Functions: `rank_jobs()` (Line 57) & `_fuzzy_dedup()` (Line 138)

#### 🗣️ What to Say to the Interviewer:
> *"Companies often post identical listings on both LinkedIn and Naukri with slightly different titles (e.g., 'Backend Engineer' vs 'Senior Backend Developer').
>
> `_fuzzy_dedup()` uses Python's `difflib.SequenceMatcher` to calculate title and company similarity. If title similarity > 80% and company similarity > 70%, it treats them as duplicate postings and keeps the one with the higher match score.
>
> Then, it applies the `MIN_MATCH_SCORE` threshold (e.g., >=65) and selects the top 10 recommendations."*

---

### Step 8: Memory Agent & 30-Day Lookback Filter

#### 📂 Open File: [`agents/memory_agent.py`](file:///d:/Job%20search%20agent/agents/memory_agent.py)
#### 🔍 Function: `filter_seen()` (Line 61)

#### 🗣️ What to Say to the Interviewer:
> *"The Memory Agent ensures the user isn't emailed the same jobs every day. It checks the `recommendations` table with a 30-day lookback window. Any job recommended within the last 30 days or explicitly marked by the user as 'not_interested' is filtered out before email dispatch."*

---

### Step 9: Notification Digest & SMTP Delivery

#### 📂 Open File: [`agents/notification_agent.py`](file:///d:/Job%20search%20agent/agents/notification_agent.py) & [`services/email_service.py`](file:///d:/Job%20search%20agent/services/email_service.py)
#### 🔍 Functions: `send_digest()` (Line 61) & `EmailService.send()` (Line 67)

#### 🗣️ What to Say to the Interviewer:
> *"Finally, `NotificationAgent` groups recommendations by platform with branded badges (LinkedIn Blue, Naukri Purple), color-coded match scores (Green for 85+, Amber for 70+), and bulleted skill gap analyses. `EmailService` sends it via Gmail SMTP over TLS using a secure App Password."*

---

## 4. Tough Interview Questions & Winning Answers

### Q1: "Why use ChromaDB + Embeddings instead of just feeding all jobs to the LLM?"
> **Answer:** *"Cost, rate limits, and latency. If we scrape 300 jobs, feeding all 300 to an LLM would take 10+ minutes and hit token rate limits. Local embedding pre-filtering via ChromaDB takes less than 2 seconds and costs $0, allowing us to spend LLM tokens only on high-confidence candidates."*

### Q2: "How do you handle bot detection on platforms like LinkedIn?"
> **Answer:** *"Three techniques:
> 1. We load persistent session cookies via `auth.json` so we don't hit repetitive login triggers.
> 2. We disable Playwright automation flags using `--disable-blink-features=AutomationControlled` and realistic User-Agents.
> 3. We introduce randomized human delays between 1.0s and 3.0s between scroll and click actions."*

### Q3: "What happens if an LLM hallucinates a high match score for an unqualified job?"
> **Answer:** *"I implemented a Hallucination Clamp in `matching_agent.py`. We compute an offline RAG similarity baseline score. If the LLM returns a score that exceeds the vector similarity score by more than 35 points, the system averages the two scores to bring it back in line with evidence."*

### Q4: "How does the agent know if a job was already emailed yesterday?"
> **Answer:** *"The `MemoryAgent` queries the `recommendations` table in SQLite for all job IDs and normalized URLs sent within a 30-day window and filters them out of the current batch."*

---

> **Tip during interview:** Keep `agents/supervisor.py` and `agents/matching_agent.py` open in your IDE tabs — those two files showcase 80% of your architectural depth! 🚀
