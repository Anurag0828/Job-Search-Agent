# Product Blueprint: Personal AI Job Search Agent

**Document Type:** Product Requirements Document (PRD)
**Prepared for:** Engineering Kickoff
**Status:** Draft v1.0
**Owner:** Product

---

## 1. Executive Summary

The **Personal AI Job Search Agent** is an autonomous system that behaves like a dedicated personal recruiter. Every day, it reviews the user's resume and skill profile, searches multiple job platforms, filters out noise and duplicates, ranks the remaining opportunities by fit, and delivers a curated shortlist by email.

**The system does not apply to jobs.** Its sole responsibility is discovery, filtering, and communication — leaving the decision to apply entirely with the user.

**Core value proposition:** Turn thousands of daily job postings across multiple platforms into a 5–10 line digest of opportunities genuinely worth the user's attention, with a clear rationale for each.

---

## 2. Problem Statement

Job seekers checking LinkedIn, Naukri, and Indeed daily face three compounding problems:

| Problem | Impact |
|---|---|
| **Volume** | Hundreds of new postings per day per platform, most irrelevant |
| **Fragmentation** | Same role often duplicated across platforms and reposted by agencies |
| **No fit signal** | Postings don't say *why* they match a specific resume, or what's missing |

The agent exists to absorb this cognitive load and return only decision-ready information.

---

## 3. Goals & Non-Goals

**Goals**
- Understand the user's resume, skills, and experience as a structured profile
- Search LinkedIn Jobs, LinkedIn Hiring Posts, Naukri, and Indeed daily
- Deduplicate and rank postings by relevance
- Deliver a daily email digest with match score, rationale, missing skills, and direct link
- Operate unattended, reusing the user's existing authenticated browser session

**Non-Goals**
- Auto-applying to jobs
- Auto-generating or submitting application materials
- Modifying the user's resume without explicit action
- Storing or transmitting login credentials

---

## 4. User Flow (End-to-End)

```
        Resume
          │
          ▼
  Resume Understanding
          │
          ▼
   Daily Scheduler (cron trigger)
          │
          ▼
     Supervisor Agent
          │
          ▼
 Platform Collector Agents
  (LinkedIn / Naukri / Indeed)
          │
          ▼
      Job Database
          │
          ▼
     Matching Engine
          │
          ▼
     Ranking Engine
          │
          ▼
  Recommendation Engine
          │
          ▼
   Email Notification
```

**Narrative:** Once configured, the user's only touchpoint with the system is the resume upload (one-time, updated as needed) and the daily email. Everything between is invisible.

---

## 5. Product Vision

The system behaves like a professional recruiter who works around the clock: reading every new posting across the user's target platforms, discarding what doesn't fit, and surfacing only what does — with the reasoning a good recruiter would give if asked "why this one?"

---

## 6. AI Agent Responsibilities

The system is organized as a multi-agent pipeline, coordinated by a supervisor. Each agent has one narrow responsibility, which keeps the system easy to extend and debug.

| Agent | Responsibility |
|---|---|
| **Supervisor Agent** | Starts the daily workflow, coordinates handoffs between agents, monitors for failures, retries or skips failed steps without halting the full pipeline |
| **Resume Understanding Agent** | Parses the resume, extracts skills/experience/seniority, produces a structured user profile that downstream agents consume |
| **Platform Collector Agents** (one per platform) | Opens a new tab using the user's existing authenticated Chrome session, runs a search against the platform, extracts structured job data, hands it to the Job Database |
| **Matching Agent** | Compares each job posting against the structured user profile, computes a similarity/fit score, identifies missing skills |
| **Ranking Agent** | Deduplicates postings (same role across platforms or reposts), orders results by relevance, applies a cutoff so only high-quality matches proceed |
| **Notification Agent** | Assembles the daily digest and sends the email |
| **Memory Agent** | Tracks what's already been recommended and what the user has marked as applied/not-interested, prevents repeat recommendations, and lets ranking improve over time based on this history |

**Design principle:** Every agent is stateless with respect to the others — it reads its inputs from the Job Database / shared state and writes its outputs back. This means any single agent can fail, be retried, or be replaced without redesigning the pipeline.

---

## 7. High-Level System Architecture

```
                         ┌───────────────────┐
                         │      Resume        │
                         └─────────┬─────────┘
                                   ▼
                         ┌───────────────────┐
                         │   Resume Parser     │
                         └─────────┬─────────┘
                                   ▼
                         ┌───────────────────┐
                         │  User Profile Store │
                         └─────────┬─────────┘
                                   ▼
                         ┌───────────────────┐
                         │  Supervisor Agent   │
                         └─────────┬─────────┘
                 ┌─────────────────┼─────────────────┐
                 ▼                 ▼                 ▼
        ┌────────────────┐┌────────────────┐┌────────────────┐
        │ LinkedIn Agent ││  Naukri Agent  ││ Indeed Agent   │
        │ (session reuse)││ (session reuse)││ (session reuse)│
        └────────┬───────┘└────────┬───────┘└────────┬───────┘
                 └─────────────────┼─────────────────┘
                                   ▼
                         ┌───────────────────┐
                         │    Job Database     │
                         └─────────┬─────────┘
                                   ▼
                         ┌───────────────────┐
                         │  Matching Engine    │
                         └─────────┬─────────┘
                                   ▼
                         ┌───────────────────┐
                         │  Ranking Engine     │
                         └─────────┬─────────┘
                                   ▼
                         ┌───────────────────┐
                         │   Email Service     │
                         └───────────────────┘
```

**Cross-cutting component (not shown per-step):** the **Memory Store**, consulted by the Ranking Engine to suppress previously-seen or already-applied postings.

---

## 8. Platform Collection Strategy

Each supported platform (LinkedIn Jobs, LinkedIn Hiring Posts, Naukri, Indeed) has its own **Collector Module**, independent of the others. This isolation means:

- A change to one platform's page structure only affects one collector, not the whole system
- New platforms (e.g., Glassdoor, Wellfound) can be added by writing a new collector against the same interface, with no changes to Matching, Ranking, or Notification
- Each collector is responsible only for: opening a tab in the user's existing authenticated browser session, running the search, and returning structured job data (title, company, location, description, link, posted date) into a common schema

**Session handling principle:** the agent reuses the user's already-logged-in Chrome profile rather than managing separate credentials, so there is no daily login step and no credential storage inside the system.

**Collector independence at a glance:**

| Platform | Collector Responsibility | Adding a New Platform Later |
|---|---|---|
| LinkedIn Jobs | Search + extract structured listings | Implement same interface: search → extract → normalize |
| LinkedIn Hiring Posts | Parse recruiter posts for role signals | Same |
| Naukri | Search + extract structured listings | Same |
| Indeed | Search + extract structured listings | Same |

---

## 9. Data Flow

```
Resume
  │
  ▼
Structured User Profile
  │
  ▼
Job Collection (per platform)
  │
  ▼
Job Database (raw + normalized postings)
  │
  ▼
Matching (score + missing skills per job)
  │
  ▼
Ranking (dedupe + prioritize)
  │
  ▼
Recommendation (final shortlist)
  │
  ▼
Email (daily digest)
```

**Email content contract** — every recommended job includes:

| Field | Description |
|---|---|
| Company | Employer name |
| Job Title | Posted role title |
| Match Score | Numeric or qualitative fit score |
| Reason | Short explanation of why it matches the profile |
| Missing Skills | Gaps between the profile and the JD |
| Direct Job Link | One-click link to the original posting |

---

## 10. Technology Overview

High-level recommendations only — implementation details are out of scope for this document.

| Layer | Recommendation |
|---|---|
| Backend | Python, FastAPI |
| Agent Orchestration | LangGraph |
| Primary Database | PostgreSQL |
| Vector Store (semantic matching) | pgvector |
| Scheduler | APScheduler |
| Dashboard (optional, internal use) | Streamlit |
| LLM Providers | OpenAI GPT, Gemini, Claude (pluggable) |

---

## 11. Product Features

| Feature | Description |
|---|---|
| Resume Intelligence | Structured extraction of skills, experience, and seniority from the resume |
| Daily Job Discovery | Automated daily run without manual triggering |
| Multi-Platform Search | Unified collection across LinkedIn, Naukri, Indeed |
| Job Ranking | Relevance-based ordering of candidate postings |
| Duplicate Removal | Cross-platform and repost deduplication |
| Daily Email Digest | Single consolidated email with the day's best matches |
| Dashboard | Optional internal view of historical recommendations |
| Application Tracking | User can mark jobs as applied/not-interested, feeding the Memory Agent |
| Memory | Learns from prior recommendations and user feedback to avoid repeats and improve ranking |
| Future Expansion | New platform collectors added without touching core pipeline |

---

## 12. Risks & Considerations

A senior PM lens on this system surfaces a few items worth flagging before build:

| Risk | Consideration |
|---|---|
| Platform Terms of Service | Automated browsing/collection against LinkedIn, Naukri, and Indeed may conflict with each platform's terms; this should be reviewed before the collectors are built, and rate-limited to behave like a single normal user, not a scraper |
| Session fragility | Reusing a live Chrome session means UI changes on any platform can silently break a collector; the Supervisor Agent's failure handling should treat a broken collector as a partial failure, not a full pipeline failure |
| Data freshness vs. noise | Overly broad searches reintroduce the volume problem the product exists to solve; ranking cutoffs should be tunable, not hardcoded |
| False negatives in matching | The Matching Agent should surface a small "borderline" tier rather than silently discarding close-fit roles |

---

## 13. Future Vision

Beyond the core discovery-and-digest loop, natural extensions include:

- **Resume customization** — tailoring resume emphasis per job family
- **Cover letter generation** — drafting a first pass per shortlisted role
- **Company research** — auto-compiled briefs on shortlisted employers
- **Interview preparation** — role-specific prep material once the user marks a job as "applied"
- **Salary estimation** — benchmarking against market data
- **Career analytics** — trends in the user's own match scores and skill-gap patterns over time

These are explicitly out of scope for v1 and listed only to inform architecture decisions that shouldn't foreclose them later.

---

## 14. Summary

This system is a **discovery and filtering layer**, not an application layer. Its success metric is simple: does the daily email contain a small number of roles genuinely worth the user's time, each with enough context to decide quickly whether to pursue it. Everything in the architecture — agent separation, session reuse, memory, ranking — exists in service of that one email.
