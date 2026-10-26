# ============================================================
# Live Demo Funnel — Fast 2-Minute Interview Walkthrough
# Displays the real data funnel, top match rationale, and noise rejection
# ============================================================

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from database.connection import get_db, init_database
from database.models import JobPostingModel, RecommendationModel, UserProfileModel
from services.resume_rag_service import get_rag_service

console = Console()

def run_funnel_demo():
    init_database()
    db = get_db()
    
    try:
        profile = db.query(UserProfileModel).first()
        total_collected = db.query(JobPostingModel).count()
        scored_jobs = db.query(JobPostingModel).filter(JobPostingModel.match_score.isnot(None)).count()
        recs_count = db.query(RecommendationModel).count()
        
        # Breakdown by platform
        linkedin_count = db.query(JobPostingModel).filter(JobPostingModel.platform == "linkedin_jobs").count()
        naukri_count = db.query(JobPostingModel).filter(JobPostingModel.platform == "naukri").count()
        
        # Get top matches
        top_matches = (
            db.query(JobPostingModel)
            .filter(JobPostingModel.match_score.isnot(None))
            .order_by(JobPostingModel.match_score.desc())
            .limit(3)
            .all()
        )
        
        # Get rejected noise jobs
        low_matches = (
            db.query(JobPostingModel)
            .filter(JobPostingModel.match_score.isnot(None))
            .filter(JobPostingModel.match_score < 30)
            .order_by(JobPostingModel.match_score.asc())
            .limit(1)
            .all()
        )

        rag = get_rag_service()
        chunks_count = rag.get_count()

        console.print("\n")
        console.print(Panel.fit(
            "[bold cyan]AI Job Search Agent — Live End-to-End Pipeline Funnel[/bold cyan]\n"
            f"[dim]Active Profile: {profile.full_name if profile else 'Anurag Sajwan'} | RAG Embeddings: {chunks_count} Resume Chunks[/dim]",
            border_style="cyan"
        ))

        # Funnel Metrics
        funnel_table = Table(title="[bold yellow]Automated Funnel Metrics (Real Database Postings)[/bold yellow]", show_header=True)
        funnel_table.add_column("Pipeline Stage", style="bold white", width=32)
        funnel_table.add_column("Count", justify="center", style="bold green", width=12)
        funnel_table.add_column("Processing Method", style="dim", width=25)
        funnel_table.add_column("Cost & Latency", justify="center", style="cyan", width=18)

        funnel_table.add_row(
            "1. Raw Jobs Scraped\n   • LinkedIn: " + str(linkedin_count) + " | Naukri: " + str(naukri_count),
            str(total_collected),
            "Playwright CDP Session",
            "~120s (Background)"
        )
        funnel_table.add_row(
            "2. Layer 1 Semantic Vector Filter\n   (Cosine similarity against ChromaDB)",
            f"{scored_jobs} shortlisted",
            "NVIDIA Nemotron / Local",
            "$0.00 (< 2s)"
        )
        funnel_table.add_row(
            "3. Layer 2 LLM Deep Analysis\n   (RAG section evidence + Guardrails)",
            f"{recs_count} recommended",
            "LLM (Gemini / NVIDIA NIM)",
            "~30s (Throttled)"
        )
        funnel_table.add_row(
            "4. Final Ranked Email Digest\n   (Deduplicated, Sorted, Contact-enriched)",
            f"Top 10 daily",
            "Jinja2 HTML via SMTP",
            "Delivered 8:00 AM"
        )
        console.print(funnel_table)
        console.print("\n")

        # Top Match Demonstration
        if top_matches:
            top = top_matches[0]
            top_panel = Panel(
                f"[bold green]Title:[/bold green] {top.title}\n"
                f"[bold green]Company:[/bold green] {top.company} | [bold]Platform:[/bold] {top.platform}\n"
                f"[bold green]Match Score:[/bold green] [bold yellow]{top.match_score:.1f} / 100[/bold yellow]\n\n"
                f"[bold]LLM Rationale & RAG Grounding:[/bold]\n"
                f"[italic]{top.match_rationale}[/italic]\n\n"
                f"[bold]HR Contact / Apply Method:[/bold] {top.hr_contact_email or 'Direct Platform Apply'}\n"
                f"[bold]Direct URL:[/bold] [link]{top.url}[/link]",
                title="[bold green]PASSED CANDIDATE (Top AI Recommendation)[/bold green]",
                border_style="green"
            )
            console.print(top_panel)

        # Rejected Noise Demonstration
        if low_matches:
            low = low_matches[0]
            low_panel = Panel(
                f"[bold red]Title:[/bold red] {low.title}\n"
                f"[bold red]Company:[/bold red] {low.company} | [bold]Platform:[/bold] {low.platform}\n"
                f"[bold red]Match Score:[/bold red] [bold red]{low.match_score:.1f} / 100 (REJECTED)[/bold red]\n\n"
                f"[bold]Rejection Rationale:[/bold]\n"
                f"[italic]{low.match_rationale}[/italic]",
                title="[bold red]FILTERED NOISE (Unrelated Job Dropped by Agent)[/bold red]",
                border_style="red"
            )
            console.print(low_panel)

    finally:
        db.close()


if __name__ == "__main__":
    run_funnel_demo()
