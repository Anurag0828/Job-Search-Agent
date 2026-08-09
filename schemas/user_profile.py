# ============================================================
# Schema: User Profile
# ============================================================
# PURPOSE:
#   Defines the EXACT SHAPE of a parsed resume.
#   When the Resume Agent finishes parsing, it returns a UserProfile object.
#   This schema validates the data — if the LLM returns garbage, we catch it here.
#
# DIFFERENCE FROM database/models.py:
#   - database/models.py defines how data is STORED (database columns)
#   - This file defines how data FLOWS between agents (validation)
#   
#   Think of it this way:
#     Pydantic schema = the FORM you fill out
#     Database model   = the FILING CABINET where the form goes
# ============================================================

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Education(BaseModel):
    """One education entry from the resume."""
    degree: str = Field(description="e.g., 'B.Tech', 'M.Sc', 'MBA'")
    field: str = Field(description="e.g., 'Computer Science', 'Electronics'")
    institution: str = Field(description="e.g., 'IIT Delhi', 'BITS Pilani'")
    year: Optional[str] = Field(default=None, description="Graduation year, e.g., '2020'")


class WorkExperience(BaseModel):
    """One work experience entry from the resume."""
    title: str = Field(description="Job title, e.g., 'Software Engineer'")
    company: str = Field(description="Company name, e.g., 'Google'")
    duration: Optional[str] = Field(default=None, description="e.g., 'Jan 2020 - Present'")
    description: Optional[str] = Field(default=None, description="Key responsibilities/achievements")


class UserProfile(BaseModel):
    """
    The structured representation of a user's resume.
    
    This is what the Resume Agent produces after parsing a PDF/DOCX resume.
    Every downstream agent (Matching, Ranking) consumes this to compare
    against job postings.
    
    EXAMPLE:
        UserProfile(
            full_name="Rahul Sharma",
            email="rahul@example.com",
            skills=["Python", "FastAPI", "PostgreSQL", "React"],
            experience_years=5.0,
            seniority="mid-senior",
            preferred_roles=["Backend Engineer", "Full Stack Developer"],
            ...
        )
    """

    # ---- Personal Information ----
    full_name: Optional[str] = Field(
        default=None,
        description="Full name as it appears on the resume"
    )
    email: Optional[str] = Field(
        default=None,
        description="Contact email from the resume"
    )
    phone: Optional[str] = Field(
        default=None,
        description="Contact phone number"
    )

    # ---- Skills & Experience ----
    skills: list[str] = Field(
        default_factory=list,
        description="All technical and professional skills mentioned in the resume"
    )
    experience_years: Optional[float] = Field(
        default=None,
        description="Total years of professional experience"
    )
    seniority: Optional[str] = Field(
        default=None,
        description="Inferred seniority level: junior, mid, senior, lead, principal"
    )

    # ---- Work History ----
    work_experience: list[WorkExperience] = Field(
        default_factory=list,
        description="List of past jobs/roles"
    )
    past_titles: list[str] = Field(
        default_factory=list,
        description="All job titles held (extracted from work history)"
    )

    # ---- Preferences ----
    preferred_roles: list[str] = Field(
        default_factory=list,
        description="What roles the user is looking for"
    )
    preferred_locations: list[str] = Field(
        default_factory=list,
        description="Where the user wants to work"
    )

    # ---- Education ----
    education: list[Education] = Field(
        default_factory=list,
        description="Educational qualifications"
    )
    certifications: list[str] = Field(
        default_factory=list,
        description="Professional certifications"
    )

    # ---- Summary ----
    summary: Optional[str] = Field(
        default=None,
        description="2-3 sentence professional summary"
    )

    # ---- Metadata ----
    raw_resume_text: Optional[str] = Field(
        default=None,
        description="The raw text extracted from the resume file"
    )
    resume_file_path: Optional[str] = Field(
        default=None,
        description="Path to the uploaded resume file"
    )
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
