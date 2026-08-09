# ============================================================
# Schema: Recommendation
# ============================================================
# PURPOSE:
#   Defines the shape of a final recommendation that appears
#   in the daily email digest.
#
#   This is the LAST data shape in the pipeline:
#     Resume → Jobs → Matching → Ranking → **Recommendation** → Email
#
# WHAT THE USER SEES:
#   Each recommendation in the email contains:
#     - Company name
#     - Job title
#     - Match score (e.g., 92%)
#     - WHY it matches their profile
#     - What skills they're missing
#     - Direct link to apply
# ============================================================

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Recommendation(BaseModel):
    """
    A single job recommendation ready for the daily email.
    
    This is the final, polished output of the entire pipeline.
    The Notification Agent reads a list of these and renders the email.
    
    EXAMPLE:
        Recommendation(
            company="Google",
            title="Senior Backend Engineer",
            location="Bangalore",
            match_score=92.0,
            rationale="Your 5 years of Python + FastAPI experience directly matches...",
            missing_skills=["Kubernetes", "gRPC"],
            job_url="https://linkedin.com/jobs/view/12345",
            platform="linkedin_jobs",
        )
    """

    # ---- Job Information ----
    company: Optional[str] = Field(
        default="Unknown Company",
        description="Company name"
    )
    title: str = Field(
        description="Job title"
    )
    location: Optional[str] = Field(
        default=None,
        description="Job location"
    )

    # ---- Match Analysis ----
    match_score: float = Field(
        description="How well this job matches (0-100)"
    )
    rationale: str = Field(
        description="Human-readable explanation of why this is a good match"
    )
    missing_skills: list[str] = Field(
        default_factory=list,
        description="Skills the user would need to learn for this role"
    )

    # ---- Link & Source ----
    job_url: str = Field(
        description="Direct link to the job posting"
    )
    platform: str = Field(
        description="Which platform: linkedin_jobs, naukri, indeed, etc."
    )

    # ---- Metadata ----
    rank_position: Optional[int] = Field(
        default=None,
        description="Position in today's ranking (1 = best match)"
    )
    job_posting_id: Optional[int] = Field(
        default=None,
        description="ID in our database (for tracking user actions)"
    )
    recommended_at: Optional[datetime] = Field(
        default=None,
        description="When this recommendation was generated"
    )


class DailyDigest(BaseModel):
    """
    The complete daily email payload.
    
    Contains all recommendations for the day plus metadata
    about the run (how many jobs were scanned, any errors, etc.)
    """

    # ---- Recommendations ----
    recommendations: list[Recommendation] = Field(
        description="Today's recommended jobs, ordered by match score"
    )

    # ---- Run Statistics (shown in email footer) ----
    total_jobs_scanned: int = Field(
        default=0,
        description="How many jobs were collected across all platforms"
    )
    platforms_searched: list[str] = Field(
        default_factory=list,
        description="Which platforms were successfully searched"
    )
    platforms_failed: list[str] = Field(
        default_factory=list,
        description="Which platforms failed (if any)"
    )

    # ---- Timing ----
    generated_at: Optional[datetime] = Field(
        default=None,
        description="When this digest was generated"
    )
    run_id: Optional[int] = Field(
        default=None,
        description="Which pipeline run produced this digest"
    )
