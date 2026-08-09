# ============================================================
# AI Job Search Agent — Command Line Interface (CLI)
# ============================================================
# PURPOSE:
#   A clean, headless CLI interface for running the AI Job Search Agent
#   without any UI or web dashboards.
#
# USAGE:
#   1. Ingest Resume into Vector DB (ChromaDB) with RAG section chunking:
#      python cli.py ingest --file "Anurag_Sajwan_Resume_Updated_July2026.pdf"
#
#   2. Check System Status & Counts:
#      python cli.py status
#
#   3. Collect Jobs from LinkedIn & Naukri:
#      python cli.py collect
#
#   4. Match Jobs using RAG Retrieval against your stored resume:
#      python cli.py match
#
#   5. Send Email Digest of Top Recommendations:
#      python cli.py email
#
#   6. Run Full End-to-End Pipeline (Collect -> Match -> Rank -> Email):
#      python cli.py run-all
# ============================================================

import os
import sys
import argparse
from typing import Optional

# Ensure project root is in Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.connection import get_db, init_database
from database.models import JobPostingModel, RecommendationModel, RunLogModel, UserProfileModel
from services.resume_rag_service import get_rag_service
from agents.supervisor import SupervisorAgent


def cmd_ingest(file_path: str):
    """Ingest a resume file into ChromaDB with semantic section chunking."""
    if not os.path.exists(file_path):
        print(f"[CLI ERROR] Resume file not found at: {file_path}")
        return

    print("=" * 60)
    print("  RESUME RAG INGESTION")
    print("=" * 60)
    init_database()
    rag = get_rag_service()
    count = rag.ingest_resume(file_path)
    print("\n[SUCCESS] Your resume has been embedded and stored in Vector DB!")
    print(f"Total semantic sections stored: {count}")
    print("Your agent will now use RAG to fetch these exact sections when matching jobs.")


def cmd_status():
    """Display counts of stored resume chunks, jobs, and recommendations."""
    print("=" * 60)
    print("  SYSTEM STATUS & DATABASE COUNTS")
    print("=" * 60)
    init_database()
    
    # ChromaDB check
    rag = get_rag_service()
    print(f"-> Vector DB Resume Chunks:  {rag.get_count()} chunks in ChromaDB")

    # SQLite check
    db = get_db()
    try:
        profile = db.query(UserProfileModel).first()
        jobs_count = db.query(JobPostingModel).count()
        matched_count = db.query(JobPostingModel).filter(JobPostingModel.match_score.isnot(None)).count()
        recs_count = db.query(RecommendationModel).count()
        
        if profile:
            print(f"-> Active Candidate Profile: {profile.full_name} ({profile.email or 'No email'})")
            print(f"   Skills Extracted:         {len(profile.skills or [])} skills")
        else:
            print(f"-> Active Candidate Profile: None (Run 'python cli.py ingest --file <resume>' first)")
            
        print(f"-> Total Jobs Collected:     {jobs_count} postings")
        print(f"-> Jobs Scored via RAG:      {matched_count} postings")
        print(f"-> Saved Recommendations:    {recs_count} recommendations")
    finally:
        db.close()
    print("=" * 60)


def cmd_collect():
    """Run job collectors (LinkedIn & Naukri)."""
    print("=" * 60)
    print("  RUNNING JOB COLLECTORS")
    print("=" * 60)
    init_database()
    sup = SupervisorAgent()
    import asyncio
    jobs = asyncio.run(sup._run_collectors())
    if jobs:
        new_count = sup._save_jobs(jobs)
        print(f"\n[SUCCESS] Collected {len(jobs)} total jobs ({new_count} new saved to database).")
    else:
        print("\n[WARNING] No jobs collected.")


def cmd_match():
    """Run RAG job matching and ranking against stored resume chunks."""
    print("=" * 60)
    print("  RUNNING RAG JOB MATCHING")
    print("=" * 60)
    init_database()
    sup = SupervisorAgent()
    sup._run_matching()
    recs = sup._run_ranking()
    print(f"\n[SUCCESS] Generated {len(recs)} top job recommendations via RAG!")


def cmd_email():
    """Send HTML email digest of top recommendations."""
    print("=" * 60)
    print("  SENDING EMAIL DIGEST")
    print("=" * 60)
    init_database()
    sup = SupervisorAgent()
    recs = sup._run_ranking()
    sent = sup._send_email(recs)
    if sent:
        print("\n[SUCCESS] Email digest sent to your inbox!")
    else:
        print("\n[WARNING] Could not send email (check EMAIL_PASSWORD / app password in .env).")


def cmd_run_all():
    """Run full automated pipeline."""
    print("=" * 60)
    print("  RUNNING FULL AUTONOMOUS PIPELINE")
    print("=" * 60)
    init_database()
    sup = SupervisorAgent()
    result = sup.run_pipeline()
    print("\n[SUCCESS] Pipeline execution complete!")
    print(f"Summary: {result}")


def cmd_login():
    """Open a visible browser for the user to log into job platforms, then save session."""
    import asyncio
    from services.browser_service import BrowserService
    asyncio.run(BrowserService.interactive_login())


def main():
    parser = argparse.ArgumentParser(description="AI Job Search Agent — Pure CLI Interface")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: login (NEW — replaces launch_chrome.bat)
    subparsers.add_parser("login", help="Log into LinkedIn/Naukri/Indeed and save session for headless use")

    # Command: ingest
    parser_ingest = subparsers.add_parser("ingest", help="Ingest resume into ChromaDB Vector DB via RAG")
    parser_ingest.add_argument("--file", "-f", required=True, help="Path to your PDF or DOCX resume")

    # Command: status
    subparsers.add_parser("status", help="Check system status and database counts")

    # Command: collect
    subparsers.add_parser("collect", help="Scrape jobs from LinkedIn, Naukri, and Indeed")

    # Command: match
    subparsers.add_parser("match", help="Match collected jobs against stored resume chunks via RAG")

    # Command: email
    subparsers.add_parser("email", help="Send email digest of top recommendations")

    # Command: run-all
    subparsers.add_parser("run-all", help="Execute full end-to-end pipeline (Collect -> Match -> Email)")

    args = parser.parse_args()

    if args.command == "login":
        cmd_login()
    elif args.command == "ingest":
        cmd_ingest(args.file)
    elif args.command == "status":
        cmd_status()
    elif args.command == "collect":
        cmd_collect()
    elif args.command == "match":
        cmd_match()
    elif args.command == "email":
        cmd_email()
    elif args.command == "run-all":
        cmd_run_all()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

