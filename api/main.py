# ============================================================
# FastAPI Application — Main Entry Point
# ============================================================
# PURPOSE:
#   This is the web server that runs the entire application.
#   It provides API endpoints for:
#     - Uploading resumes
#     - Viewing jobs and recommendations
#     - Manually triggering pipeline runs
#
# HOW TO RUN:
#   cd "d:\Job search agent"
#   .\venv\Scripts\python.exe -m uvicorn api.main:app --reload
#
#   Then open: http://localhost:8000
#   API docs:  http://localhost:8000/docs (interactive Swagger UI)
#
# ARCHITECTURE:
#   This file creates the FastAPI app and registers all routes.
#   Routes are defined in separate files under api/routes/ for organization.
#   
#   api/main.py          ← You are here (app creation + startup)
#   api/routes/resume.py ← Resume upload/view endpoints
#   api/routes/jobs.py   ← Job listing endpoints (Phase 3+)
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.connection import init_database

# Import route modules
from api.routes import resume as resume_routes
from api.routes import jobs as jobs_routes


# ---- Create the FastAPI Application ----
app = FastAPI(
    title="AI Job Search Agent",
    description=(
        "Your personal AI recruiter — parses resumes, searches job platforms, "
        "and delivers daily email digests of the best matching opportunities."
    ),
    version="1.0.0",
)


# ---- CORS Middleware ----
# Allows the frontend (Streamlit dashboard, etc.) to make API calls.
# Without this, browser security would block requests from the dashboard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # In production, restrict this to your domain
    allow_credentials=True,
    allow_methods=["*"],        # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],        # Allow all headers
)


# ---- Register Route Modules ----
# Each module adds its own endpoints to the app.
# prefix="/api/resume" means all resume routes start with /api/resume
app.include_router(
    resume_routes.router,
    prefix="/api/resume",
    tags=["Resume"],            # Groups endpoints in the docs UI
)

app.include_router(
    jobs_routes.router,
    prefix="/api/jobs",
    tags=["Jobs & Recommendations"],
)


# ---- Startup Event ----
# This runs ONCE when the server starts up.
@app.on_event("startup")
async def startup():
    """
    Initialize the application on startup.
    
    This:
    1. Creates database tables if they don't exist
    2. Logs that the server is ready
    """
    print("=" * 50)
    print("  AI Job Search Agent - Starting Up")
    print("=" * 50)
    init_database()
    print("[OK] Server is ready!")
    print("  API docs: http://localhost:8000/docs")
    print("=" * 50)


# ---- Health Check Endpoint ----
@app.get("/", tags=["Health"])
async def health_check():
    """
    Simple health check endpoint.
    
    Visit http://localhost:8000/ to verify the server is running.
    """
    return {
        "status": "running",
        "service": "AI Job Search Agent",
        "version": "1.0.0",
    }


@app.get("/api/health", tags=["Health"])
async def api_health():
    """
    API health check with more details.
    
    Returns the current configuration (without secrets).
    """
    from config.settings import settings
    return {
        "status": "healthy",
        "llm_provider": settings.LLM_PROVIDER,
        "database": "sqlite" if "sqlite" in settings.DATABASE_URL else "postgresql",
        "platforms": {
            "linkedin_jobs": settings.ENABLE_LINKEDIN_JOBS,
            "linkedin_posts": settings.ENABLE_LINKEDIN_POSTS,
            "naukri": settings.ENABLE_NAUKRI,
            "indeed": settings.ENABLE_INDEED,
        },
    }
