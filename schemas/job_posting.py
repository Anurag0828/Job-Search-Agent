# ============================================================
# Schema: Job Posting
# ============================================================
# PURPOSE:
#   Defines the EXACT SHAPE of a job posting.
#   Every collector (LinkedIn, Naukri, Indeed) must produce data
#   in this shape. This is the "contract" that keeps collectors
#   interchangeable.
#
# WHY THIS MATTERS:
#   If LinkedIn returns {title: "Engineer"} and Naukri returns
#   {job_name: "Engineer"}, downstream agents would break.
#   This schema forces BOTH to produce {title: "Engineer"}.
#
#   LinkedIn Collector ──→ JobPosting ──→ Database
#   Naukri Collector   ──→ JobPosting ──→ Database
#   Indeed Collector   ──→ JobPosting ──→ Database
#                          ↑ SAME SHAPE — enforced by this file
# ============================================================

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class JobPosting(BaseModel):
    """
    A single job posting, normalized to a common format.
    
    Every collector transforms platform-specific data into this shape.
    The Matching Agent reads these to compute fit scores.
    
    EXAMPLE:
        JobPosting(
            title="Senior Backend Engineer",
            company="Google",
            location="Bangalore, India",
            description="We're looking for a Python expert...",
            url="https://linkedin.com/jobs/view/12345",
            platform="linkedin_jobs",
            posted_date="2 days ago",
        )
    """

    # ---- Core Job Details ----
    title: str = Field(
        description="Job title as posted on the platform"
    )
    company: Optional[str] = Field(
        default=None,
        description="Employer/company name"
    )
    location: Optional[str] = Field(
        default=None,
        description="Job location (city, state, or 'Remote')"
    )
    description: Optional[str] = Field(
        default=None,
        description="Full job description text"
    )
    url: str = Field(
        description="Direct link to the original job posting"
    )

    # ---- Additional Details (may not always be available) ----
    posted_date: Optional[str] = Field(
        default=None,
        description="When the job was posted (e.g., '2 days ago', '2024-01-15')"
    )
    salary: Optional[str] = Field(
        default=None,
        description="Salary range if displayed (e.g., '₹15-25 LPA')"
    )
    job_type: Optional[str] = Field(
        default=None,
        description="full-time, part-time, contract, internship"
    )
    work_mode: Optional[str] = Field(
        default=None,
        description="remote, hybrid, onsite"
    )

    # ---- Source Tracking ----
    platform: str = Field(
        description="Which platform this came from: linkedin_jobs, linkedin_posts, naukri, indeed"
    )
    platform_job_id: Optional[str] = Field(
        default=None,
        description="Unique ID on the source platform (for dedup and re-collection avoidance)"
    )

    # ---- Collection Metadata ----
    collected_at: Optional[datetime] = Field(
        default=None,
        description="When our system collected this posting"
    )


class JobPostingWithScore(JobPosting):
    """
    A job posting AFTER the Matching Agent has scored it.
    
    Extends JobPosting with match-specific fields.
    This is what flows from the Matching Agent to the Ranking Agent.
    """

    # ---- Matching Results ----
    match_score: float = Field(
        description="How well this job matches the user's profile (0-100)"
    )
    match_rationale: Optional[str] = Field(
        default=None,
        description="Why this job matches (human-readable explanation)"
    )
    missing_skills: list[str] = Field(
        default_factory=list,
        description="Skills required by the job but not in the user's profile"
    )
