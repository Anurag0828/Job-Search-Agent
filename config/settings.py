# ============================================================
# AI Job Search Agent — Configuration Settings
# ============================================================
# PURPOSE:
#   This is the SINGLE SOURCE OF TRUTH for all configuration.
#   Every other file in the project imports from here:
#       from config.settings import settings
#
#   This file reads your .env file and exposes typed, validated settings.
#   If a required setting is missing, the app will fail IMMEDIATELY with
#   a clear error message — not silently break 5 steps into the pipeline.
# ============================================================

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """
    All application settings, loaded from .env file.
    
    HOW TO USE in other files:
        from config.settings import settings
        
        api_key = settings.OPENAI_API_KEY
        db_url  = settings.DATABASE_URL
    """

    # ---- LLM Configuration ----
    # Which AI provider to use: "openai", "gemini", or "claude"
    LLM_PROVIDER: str = Field(
        default="openai",
        description="Which LLM to use. Options: openai, gemini, claude"
    )

    # OpenAI settings
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="Your OpenAI API key (starts with sk-...)"
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o",
        description="Which OpenAI model to use"
    )

    # Google Gemini settings
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Your Google Gemini API key"
    )
    GEMINI_MODEL: str = Field(
        default="gemini-1.5-pro",
        description="Which Gemini model to use"
    )

    # Anthropic Claude settings
    CLAUDE_API_KEY: Optional[str] = Field(
        default=None,
        description="Your Anthropic Claude API key"
    )
    CLAUDE_MODEL: str = Field(
        default="claude-sonnet-4-20250514",
        description="Which Claude model to use"
    )

    # NVIDIA NIM settings
    NVIDIA_API_KEY: Optional[str] = Field(
        default=None,
        description="Your NVIDIA NIM API key (starts with nvapi-...)"
    )
    NVIDIA_MODEL: str = Field(
        default="meta/llama-3.1-70b-instruct",
        description="Which NVIDIA NIM model to use"
    )

    # ---- Embeddings ----
    EMBEDDING_PROVIDER: str = Field(
        default="local",
        description="Which embedding provider: 'local' (sentence-transformers) or 'nvidia' (NVIDIA NIM)"
    )
    NVIDIA_EMBED_MODEL: str = Field(
        default="nvidia/nemotron-3-embed-1b",
        description="Which NVIDIA embedding model to use"
    )

    # ---- Database ----
    DATABASE_URL: str = Field(
        default="sqlite:///./data/jobsearch.db",
        description="Database connection string. SQLite by default, can be PostgreSQL"
    )

    # ---- Email ----
    EMAIL_SENDER: str = Field(
        default="",
        description="Gmail address to send from"
    )
    EMAIL_PASSWORD: str = Field(
        default="",
        description="Gmail App Password (NOT your regular password)"
    )
    EMAIL_RECIPIENT: str = Field(
        default="",
        description="Email address to receive the daily digest"
    )
    EMAIL_SMTP_HOST: str = Field(
        default="smtp.gmail.com",
        description="SMTP server hostname"
    )
    EMAIL_SMTP_PORT: int = Field(
        default=587,
        description="SMTP server port (587 for TLS)"
    )

    # ---- Browser Automation ----
    CHROME_DEBUG_PORT: int = Field(
        default=9222,
        description="Port for Chrome remote debugging connection"
    )

    # ---- Job Search Preferences ----
    SEARCH_QUERIES: str = Field(
        default="AI Engineer,LLM Engineer,GenAI Engineer,RAG Engineer,Python AI Developer",
        description="Comma-separated job titles to search for"
    )
    SEARCH_LOCATIONS: str = Field(
        default="Dehradun,Bangalore,Remote,India",
        description="Comma-separated preferred locations"
    )

    # ---- Scheduling ----
    SCHEDULE_HOUR: int = Field(
        default=8,
        description="Hour of day (0-23) to run the daily search"
    )
    SCHEDULE_MINUTE: int = Field(
        default=0,
        description="Minute (0-59) to run the daily search"
    )

    # ---- Matching & Ranking ----
    MIN_MATCH_SCORE: int = Field(
        default=65,
        description="Minimum match score (0-100) to include in recommendations"
    )
    MAX_RECOMMENDATIONS: int = Field(
        default=10,
        description="Maximum number of jobs to include in the daily email"
    )

    # ---- Platform Toggles ----
    ENABLE_LINKEDIN_JOBS: bool = Field(default=True)
    ENABLE_LINKEDIN_POSTS: bool = Field(default=True)
    ENABLE_NAUKRI: bool = Field(default=True)
    ENABLE_INDEED: bool = Field(default=True)

    # ---- Logging ----
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR"
    )

    # ---- Computed Properties ----
    # These are helper methods that derive values from the raw settings

    @property
    def search_queries_list(self) -> list[str]:
        """
        Converts the comma-separated SEARCH_QUERIES string into a Python list.
        
        Example:
            .env has:  SEARCH_QUERIES=Backend Engineer,Python Developer
            This returns: ["Backend Engineer", "Python Developer"]
        """
        return [query.strip() for query in self.SEARCH_QUERIES.split(",")]

    @property
    def search_locations_list(self) -> list[str]:
        """
        Converts the comma-separated SEARCH_LOCATIONS string into a Python list.
        
        Example:
            .env has:  SEARCH_LOCATIONS=Bangalore,Remote
            This returns: ["Bangalore", "Remote"]
        """
        return [loc.strip() for loc in self.SEARCH_LOCATIONS.split(",")]

    class Config:
        # Tell pydantic-settings to load from .env file
        env_file = ".env"
        # If .env doesn't exist, don't crash — use defaults
        env_file_encoding = "utf-8"
        # Allow extra fields (future-proofing)
        extra = "ignore"


# ============================================================
# CREATE THE GLOBAL SETTINGS INSTANCE
# ============================================================
# This is what every other file imports:
#     from config.settings import settings
#
# It reads .env ONCE when the app starts, then reuses the same
# settings object everywhere. No repeated file reads.
# ============================================================
settings = Settings()
