# ============================================================
# Database Models — Table Definitions
# ============================================================
# PURPOSE:
#   Defines the structure of every table in our database.
#   Each class below = one table. Each attribute = one column.
#
# HOW TO READ:
#   class JobPosting(Base):                  ← This is a table called "job_postings"
#       __tablename__ = "job_postings"
#       id = Column(Integer, primary_key=True)  ← Auto-incrementing ID column
#       title = Column(String, nullable=False)   ← Required text column
#       company = Column(String)                  ← Optional text column
#
# TABLES WE DEFINE:
#   1. user_profiles     — The user's parsed resume data
#   2. job_postings      — Every job collected from platforms
#   3. recommendations   — Jobs that were recommended + user's response
#   4. run_logs          — History of each daily pipeline run
# ============================================================

from sqlalchemy import (
    Column,         # Defines a column in a table
    Integer,        # Column type: whole numbers (1, 2, 3...)
    String,         # Column type: text
    Text,           # Column type: long text (for job descriptions)
    Float,          # Column type: decimal numbers (match scores like 85.5)
    Boolean,        # Column type: true/false
    DateTime,       # Column type: dates and times
    JSON,           # Column type: structured data (lists, dicts)
)
from sqlalchemy.sql import func  # For auto-generating timestamps
from database.connection import Base


# ============================================================
# TABLE 1: User Profiles
# ============================================================
# Stores the structured data extracted from the user's resume.
# There's typically just ONE row here (one user), but we support
# multiple profiles for future multi-user support.
# ============================================================

class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    # ---- Identity ----
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ---- Extracted Resume Data ----
    # Full name from the resume
    full_name = Column(String(200), nullable=True)

    # Contact email from the resume
    email = Column(String(200), nullable=True)

    # Phone number from the resume
    phone = Column(String(50), nullable=True)

    # Skills as a JSON list: ["Python", "FastAPI", "SQL", "React"]
    skills = Column(JSON, nullable=True)

    # Total years of professional experience
    experience_years = Column(Float, nullable=True)

    # Seniority level: "junior", "mid", "senior", "lead", "principal"
    seniority = Column(String(50), nullable=True)

    # Job titles the user has held: ["Software Engineer", "Backend Developer"]
    past_titles = Column(JSON, nullable=True)

    # What roles the user is looking for: ["Full Stack Developer", "Backend Engineer"]
    preferred_roles = Column(JSON, nullable=True)

    # Preferred work locations: ["Bangalore", "Remote"]
    preferred_locations = Column(JSON, nullable=True)

    # Education history as JSON: [{"degree": "B.Tech", "field": "CS", "institution": "..."}]
    education = Column(JSON, nullable=True)

    # Certifications: ["AWS Certified", "Google Cloud Professional"]
    certifications = Column(JSON, nullable=True)

    # Brief professional summary (2-3 sentences)
    summary = Column(Text, nullable=True)

    # The raw text extracted from the resume file (kept for re-processing)
    raw_resume_text = Column(Text, nullable=True)

    # Path to the uploaded resume file
    resume_file_path = Column(String(500), nullable=True)

    # ---- Metadata ----
    # When this profile was first created
    created_at = Column(DateTime, server_default=func.now())
    # When this profile was last updated (auto-updates on change)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<UserProfile(id={self.id}, name='{self.full_name}', seniority='{self.seniority}')>"


# ============================================================
# TABLE 2: Job Postings
# ============================================================
# Every job collected from every platform lands here.
# This is the CENTRAL HUB of the system — collectors write to it,
# matching/ranking read from it.
# ============================================================

class JobPostingModel(Base):
    __tablename__ = "job_postings"

    # ---- Identity ----
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ---- Job Details (from the platform) ----
    # Job title as posted (e.g., "Senior Backend Engineer")
    title = Column(String(500), nullable=False)

    # Company name (e.g., "Google")
    company = Column(String(300), nullable=True)

    # Job location (e.g., "Bangalore, India" or "Remote")
    location = Column(String(300), nullable=True)

    # Full job description text
    description = Column(Text, nullable=True)

    # Direct URL to the job posting
    url = Column(String(1000), nullable=False)

    # When the job was posted on the platform
    posted_date = Column(String(100), nullable=True)

    # Salary range if available (e.g., "₹15-25 LPA")
    salary = Column(String(200), nullable=True)

    # Job type: "full-time", "part-time", "contract", "internship"
    job_type = Column(String(50), nullable=True)

    # Work mode: "remote", "hybrid", "onsite"
    work_mode = Column(String(50), nullable=True)

    # ---- Source Tracking ----
    # Which platform this came from: "linkedin_jobs", "linkedin_posts", "naukri", "indeed"
    platform = Column(String(50), nullable=False)

    # Unique identifier on the source platform (to avoid re-collecting)
    platform_job_id = Column(String(200), nullable=True)

    # ---- Matching Data (filled by Matching Agent) ----
    # Match score from 0-100 (NULL until matching runs)
    match_score = Column(Float, nullable=True)

    # Why this job matches the user's profile
    match_rationale = Column(Text, nullable=True)

    # Skills required by the job but missing from user's profile
    missing_skills = Column(JSON, nullable=True)

    # ---- HR Contact & Application Info (filled by ContactExtractor) ----
    # HR email address extracted from job description (e.g., "hr@company.com")
    hr_contact_email = Column(String(300), nullable=True)

    # How to apply: "Email resume to hr@x.com", "DM recruiter on LinkedIn", "Apply via portal"
    application_method = Column(String(500), nullable=True)

    # How many hours ago this job was posted (for recency scoring)
    posted_hours_ago = Column(Integer, nullable=True)

    # Whether this is an urgent hire ("ASAP", "Immediate joining", etc.)
    is_urgent = Column(Boolean, default=False)

    # ---- Deduplication ----
    # Has this job been identified as a duplicate of another?
    is_duplicate = Column(Boolean, default=False)

    # If duplicate, which job_posting.id is it a duplicate of?
    duplicate_of_id = Column(Integer, nullable=True)

    # ---- Status ----
    # Has this job been included in a recommendation email?
    is_recommended = Column(Boolean, default=False)

    # User's action: NULL (no action), "applied", "not_interested", "saved"
    user_action = Column(String(50), nullable=True)

    # ---- Metadata ----
    # When this job was collected by our system
    collected_at = Column(DateTime, server_default=func.now())

    # Which daily run collected this job
    run_id = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<JobPosting(id={self.id}, title='{self.title}', company='{self.company}', platform='{self.platform}')>"


# ============================================================
# TABLE 3: Recommendations
# ============================================================
# Tracks every recommendation sent to the user.
# This is what the Memory Agent reads to avoid repeat recommendations.
# ============================================================

class RecommendationModel(Base):
    __tablename__ = "recommendations"

    # ---- Identity ----
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ---- Link to the job ----
    # Which job posting this recommendation is about
    job_posting_id = Column(Integer, nullable=False)

    # ---- Recommendation Details ----
    # Match score at the time of recommendation
    match_score = Column(Float, nullable=False)

    # Why we recommended this job
    rationale = Column(Text, nullable=True)

    # Skills the user is missing for this job
    missing_skills = Column(JSON, nullable=True)

    # Position in the email (1 = top recommendation)
    rank_position = Column(Integer, nullable=True)

    # ---- User Response ----
    # Did the user act on this? "applied", "not_interested", "saved", NULL
    user_action = Column(String(50), nullable=True)

    # ---- Metadata ----
    # When this recommendation was sent
    recommended_at = Column(DateTime, server_default=func.now())

    # Which daily run generated this recommendation
    run_id = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<Recommendation(id={self.id}, job_id={self.job_posting_id}, score={self.match_score})>"


# ============================================================
# TABLE 4: Run Logs
# ============================================================
# Tracks every daily pipeline run — when it started, if it succeeded,
# what errors occurred, how many jobs were found, etc.
# ============================================================

class RunLogModel(Base):
    __tablename__ = "run_logs"

    # ---- Identity ----
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ---- Timing ----
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    # ---- Status ----
    # "running", "completed", "partial_failure", "failed"
    status = Column(String(50), default="running")

    # ---- Statistics ----
    # How many jobs were collected across all platforms
    jobs_collected = Column(Integer, default=0)

    # How many jobs were new (not previously seen)
    jobs_new = Column(Integer, default=0)

    # How many jobs were matched (scored)
    jobs_matched = Column(Integer, default=0)

    # How many recommendations were sent in the email
    recommendations_sent = Column(Integer, default=0)

    # ---- Error Tracking ----
    # Which collectors failed (if any): {"linkedin_jobs": "timeout", "naukri": null, ...}
    collector_errors = Column(JSON, nullable=True)

    # General error message if the whole run failed
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<RunLog(id={self.id}, status='{self.status}', jobs_collected={self.jobs_collected})>"
