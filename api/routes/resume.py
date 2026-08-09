# ============================================================
# API Routes: Resume Upload & Management
# ============================================================
# PURPOSE:
#   Provides endpoints for uploading resumes and viewing
#   the parsed user profile.
#
# ENDPOINTS:
#   POST /api/resume/upload  — Upload a new resume file (PDF/DOCX)
#   GET  /api/resume/profile — View the current parsed profile
#
# HOW IT CONNECTS:
#   User uploads file → API receives file → saves to disk
#                     → calls ResumeAgent.parse_resume()
#                     → ResumeAgent extracts text → sends to LLM
#                     → LLM returns structured data → saves to DB
#                     → returns profile to user
# ============================================================

import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from agents.resume_agent import ResumeAgent
from schemas.user_profile import UserProfile
from typing import Optional


# Create a router — this groups all resume-related endpoints
router = APIRouter()

# Directory where uploaded resumes are saved
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")

# Ensure the uploads directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=dict)
async def upload_resume(file: UploadFile = File(...)):
    """
    Upload a resume file (PDF or DOCX) for parsing.
    
    This endpoint:
    1. Receives the uploaded file
    2. Validates it's a PDF or DOCX
    3. Saves it to the uploads/ directory
    4. Calls the Resume Agent to parse it
    5. Returns the extracted profile data
    
    Request:
        POST /api/resume/upload
        Content-Type: multipart/form-data
        Body: file=resume.pdf
    
    Response:
        {
            "status": "success",
            "message": "Resume parsed successfully",
            "profile": {
                "full_name": "Rahul Sharma",
                "skills": ["Python", "FastAPI", ...],
                ...
            }
        }
    """
    # ---- Step 1: Validate file type ----
    filename = file.filename or "unknown"
    extension = os.path.splitext(filename)[1].lower()

    if extension not in [".pdf", ".docx"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {extension}. Please upload a .pdf or .docx file."
        )

    # ---- Step 2: Save the file to disk ----
    # We save it so we can re-process it later if needed
    save_path = os.path.join(UPLOAD_DIR, f"resume{extension}")

    try:
        with open(save_path, "wb") as buffer:
            # Read the uploaded file in chunks and write to disk
            shutil.copyfileobj(file.file, buffer)
        print(f"[API] Resume saved to: {save_path}")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded file: {str(e)}"
        )

    # ---- Step 3: Parse the resume using the Resume Agent ----
    try:
        agent = ResumeAgent()
        profile = agent.parse_resume(save_path)

        return {
            "status": "success",
            "message": "Resume parsed successfully",
            "profile": profile.model_dump(
                # Exclude the raw resume text from the response
                # (it's saved in DB but too large to return)
                exclude={"raw_resume_text"}
            ),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse resume: {str(e)}"
        )


@router.get("/profile", response_model=dict)
async def get_profile():
    """
    Get the current user profile (parsed from the most recent resume).
    
    Returns the structured profile data that was extracted from the
    last uploaded resume. Returns a message if no resume has been
    uploaded yet.
    
    Request:
        GET /api/resume/profile
    
    Response:
        {
            "status": "success",
            "profile": {
                "full_name": "Rahul Sharma",
                "skills": ["Python", "FastAPI", ...],
                "experience_years": 5.0,
                ...
            }
        }
    """
    profile = ResumeAgent.get_current_profile()

    if profile is None:
        return {
            "status": "no_profile",
            "message": "No resume has been uploaded yet. Please upload a resume first.",
            "profile": None,
        }

    return {
        "status": "success",
        "profile": profile.model_dump(exclude={"raw_resume_text"}),
    }
