# ============================================================
# Supervisor Agent — Orchestrates the Entire Pipeline
# ============================================================
# PURPOSE:
#   The "brain" that runs the full daily pipeline from start to finish.
#   Coordinates all agents and collectors in the correct order.
#
# PIPELINE (what happens on each daily run):
#
#   START
#     │
#     ├─ Step 1: Load user profile
#     │
#     ├─ Step 2: Run collectors (LinkedIn, Naukri)
#     │          Each collector opens a Chrome tab, searches, extracts jobs
#     │          If one fails, the others continue (fault-tolerant)
#     │
#     ├─ Step 3: Save collected jobs to database
#     │
#     ├─ Step 4: Run Matching Agent (vector pre-filter → LLM analysis)
#     │
#     ├─ Step 5: Run Ranking Agent (dedup → sort → cutoff)
#     │
#     ├─ Step 6: Run Memory Agent (remove previously-recommended jobs)
#     │
#     ├─ Step 7: Send email digest via Notification Agent
#     │
#     └─ Step 8: Log the run results
#   END
#
# FAULT TOLERANCE:
#   - If LinkedIn fails → log error, continue with Naukri
#   - If matching fails for one job → skip it, continue with others
#   - If email fails → save recommendations, try again tomorrow
#   - Every step is wrapped in try/except
# ============================================================

import asyncio
from datetime import datetime
from typing import Optional
from database.connection import get_db
from database.models import RunLogModel, JobPostingModel, UserProfileModel
from config.settings import settings


class SupervisorAgent:
    """
    Orchestrates the complete daily job search pipeline.
    
    Usage:
        supervisor = SupervisorAgent()
        
        # Run the full pipeline
        success = supervisor.run_pipeline()
        
        # Or run individual steps
        supervisor.run_collectors_only()
        supervisor.run_matching_only()
    """

    def __init__(self):
        """Initialize the supervisor. Services are lazy-loaded."""
        self._run_id: Optional[int] = None
        self._stats = {
            "jobs_collected": 0,
            "jobs_new": 0,
            "jobs_matched": 0,
            "recommendations_sent": 0,
            "collector_errors": {},
            "platforms_searched": [],
            "platforms_failed": [],
        }

    # ================================================================
    # MAIN METHOD — Run the full pipeline
    # ================================================================

    def run_pipeline(self) -> bool:
        """
        Run the complete daily pipeline synchronously.
        
        This is the main entry point. It:
        1. Creates a run log
        2. Checks for a user profile
        3. Runs collectors (async → sync bridge)
        4. Runs matching, ranking, memory
        5. Sends email
        6. Updates the run log
        
        Returns:
            True if the pipeline completed (even partially), False on total failure
        """
        print("\n" + "=" * 60)
        print("  SUPERVISOR — Daily Pipeline Starting")
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Step 0: Create a run log entry
        self._run_id = self._create_run_log()

        try:
            # Step 1: Check for user profile
            if not self._check_profile():
                self._update_run_log("failed", "No user profile found. Upload a resume first.")
                return False

            # Step 2: Run collectors (browser-based, async)
            print("\n--- Step 2: Collecting Jobs ---")
            collected_jobs = asyncio.run(self._run_collectors())
            print(f"[Supervisor] Collected {len(collected_jobs)} total jobs")

            # Step 3: Save collected jobs to database
            if collected_jobs:
                new_count = self._save_jobs(collected_jobs)
                self._stats["jobs_collected"] = len(collected_jobs)
                self._stats["jobs_new"] = new_count
                print(f"[Supervisor] Saved {new_count} new jobs to database")

            # Step 4: Run Matching Agent
            print("\n--- Step 4: Matching Jobs ---")
            scored_jobs = self._run_matching()
            self._stats["jobs_matched"] = len(scored_jobs)

            # Step 5: Run Ranking Agent
            print("\n--- Step 5: Ranking Jobs ---")
            recommendations = self._run_ranking(self._run_id)

            # Step 6: Run Memory Agent
            print("\n--- Step 6: Filtering Seen Jobs ---")
            final_recs = self._run_memory(recommendations)

            # Step 7: Send Email
            print("\n--- Step 7: Sending Email ---")
            if final_recs:
                email_sent = self._send_email(final_recs)
                if email_sent:
                    self._stats["recommendations_sent"] = len(final_recs)
            else:
                print("[Supervisor] No new matching jobs found. Skipping email.")
                email_sent = True # Consider it a success if we didn't crash

            # Step 8: Update run log
            status = "completed" if email_sent else "partial_failure"
            self._update_run_log(status)

            # Print summary
            self._print_summary()
            return True

        except Exception as e:
            print(f"\n[Supervisor] PIPELINE FAILED: {str(e)}")
            self._update_run_log("failed", str(e))
            return False

    # ================================================================
    # STEP 1: Check Profile
    # ================================================================

    def _check_profile(self) -> bool:
        """Verify that a user profile exists in the database."""
        db = get_db()
        try:
            profile = db.query(UserProfileModel).first()
            if profile:
                print(f"[Supervisor] Profile found: {profile.full_name} "
                      f"({len(profile.skills or [])} skills)")
                return True
            return False
        finally:
            db.close()

    # ================================================================
    # STEP 2: Run Collectors (async)
    # ================================================================

    async def _run_collectors(self) -> list[dict]:
        """
        Run all enabled collectors and gather job listings.
        
        Each collector runs in sequence (not parallel) to avoid
        overwhelming Chrome with too many tabs and to respect
        rate limits on job platforms.
        """
        from services.browser_service import BrowserService
        from collectors.linkedin_jobs import LinkedInJobsCollector
        from collectors.naukri import NaukriCollector

        all_jobs = []
        search_queries = [q.strip() for q in settings.SEARCH_QUERIES.split(",")]
        search_locations = [l.strip() for l in settings.SEARCH_LOCATIONS.split(",")]

        async with BrowserService() as browser:
            # --- LinkedIn Jobs ---
            if settings.ENABLE_LINKEDIN_JOBS:
                try:
                    print("\n[Supervisor] Running LinkedIn Jobs collector...")
                    collector = LinkedInJobsCollector(browser)
                    jobs = await collector.collect_multiple_queries(
                        queries=search_queries,
                        locations=search_locations,
                        max_pages=2,
                    )
                    all_jobs.extend([self._job_posting_to_dict(j) for j in jobs])
                    self._stats["platforms_searched"].append("linkedin_jobs")
                    print(f"[Supervisor] LinkedIn: {len(jobs)} jobs collected")
                except Exception as e:
                    print(f"[Supervisor] LinkedIn FAILED: {str(e)}")
                    self._stats["collector_errors"]["linkedin_jobs"] = str(e)
                    self._stats["platforms_failed"].append("linkedin_jobs")

            # --- Naukri ---
            if settings.ENABLE_NAUKRI:
                try:
                    print("\n[Supervisor] Running Naukri collector...")
                    collector = NaukriCollector(browser)
                    jobs = await collector.collect_multiple_queries(
                        queries=search_queries,
                        locations=search_locations,
                        max_pages=2,
                    )
                    all_jobs.extend([self._job_posting_to_dict(j) for j in jobs])
                    self._stats["platforms_searched"].append("naukri")
                    print(f"[Supervisor] Naukri: {len(jobs)} jobs collected")
                except Exception as e:
                    print(f"[Supervisor] Naukri FAILED: {str(e)}")
                    self._stats["collector_errors"]["naukri"] = str(e)
                    self._stats["platforms_failed"].append("naukri")

            # --- Indeed ---
            if settings.ENABLE_INDEED:
                try:
                    print("\n[Supervisor] Running Indeed collector...")
                    from collectors.indeed import IndeedCollector
                    collector = IndeedCollector(browser)
                    jobs = await collector.collect_multiple_queries(
                        queries=search_queries,
                        locations=search_locations,
                        max_pages=2,
                    )
                    all_jobs.extend([self._job_posting_to_dict(j) for j in jobs])
                    self._stats["platforms_searched"].append("indeed")
                    print(f"[Supervisor] Indeed: {len(jobs)} jobs collected")
                except Exception as e:
                    print(f"[Supervisor] Indeed FAILED: {str(e)}")
                    self._stats["collector_errors"]["indeed"] = str(e)
                    self._stats["platforms_failed"].append("indeed")

        return all_jobs

    def _job_posting_to_dict(self, job_posting) -> dict:
        """Convert a JobPosting schema to a plain dict for database saving."""
        return job_posting.model_dump()

    # ================================================================
    # STEP 3: Save Jobs to Database
    # ================================================================

    def _save_jobs(self, jobs: list[dict]) -> int:
        """
        Save collected jobs to the database.
        Skips jobs that already exist (based on URL).
        Returns the number of NEW jobs saved.
        """
        db = get_db()
        new_count = 0
        try:
            for job_dict in jobs:
                # Check if this job already exists (by URL)
                existing = db.query(JobPostingModel).filter(
                    JobPostingModel.url == job_dict.get("url")
                ).first()

                if existing:
                    continue  # Skip — already in database

                db_job = JobPostingModel(
                    title=job_dict.get("title", ""),
                    company=job_dict.get("company"),
                    location=job_dict.get("location"),
                    description=job_dict.get("description"),
                    url=job_dict.get("url", ""),
                    posted_date=job_dict.get("posted_date"),
                    salary=job_dict.get("salary"),
                    job_type=job_dict.get("job_type"),
                    work_mode=job_dict.get("work_mode"),
                    platform=job_dict.get("platform", "unknown"),
                    platform_job_id=job_dict.get("platform_job_id"),
                    run_id=self._run_id,
                )
                db.add(db_job)
                new_count += 1

            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[Supervisor] Error saving jobs: {e}")
        finally:
            db.close()

        return new_count

    # ================================================================
    # STEP 4: Run Matching
    # ================================================================

    def _run_matching(self) -> list:
        """Run the Matching Agent on unmatched jobs."""
        from agents.matching_agent import MatchingAgent
        try:
            agent = MatchingAgent()
            return agent.match_jobs()
        except Exception as e:
            print(f"[Supervisor] Matching failed: {e}")
            return []

    # ================================================================
    # STEP 5: Run Ranking
    # ================================================================

    def _run_ranking(self, run_id: int = None) -> list:
        """Run the Ranking Agent to sort and filter scored jobs."""
        from agents.ranking_agent import RankingAgent
        try:
            agent = RankingAgent()
            return agent.rank_jobs(run_id=run_id)
        except Exception as e:
            print(f"[Supervisor] Ranking failed: {e}")
            return []

    # ================================================================
    # STEP 6: Run Memory
    # ================================================================

    def _run_memory(self, recommendations: list) -> list:
        """Run the Memory Agent to filter out previously-seen jobs."""
        from agents.memory_agent import MemoryAgent
        try:
            agent = MemoryAgent()
            filtered = agent.filter_seen(recommendations)
            # Record these recommendations for future memory
            agent.record_recommendations(filtered, run_id=self._run_id)
            return filtered
        except Exception as e:
            print(f"[Supervisor] Memory agent failed: {e}")
            return recommendations  # Return unfiltered if memory fails

    # ================================================================
    # STEP 7: Send Email
    # ================================================================

    def _send_email(self, recommendations: list) -> bool:
        """Send the daily digest email."""
        from agents.notification_agent import NotificationAgent
        if not recommendations:
            print("[Supervisor] No recommendations to email")
            return True  # Not a failure — just nothing to send

        try:
            agent = NotificationAgent()
            return agent.send_digest(
                recommendations=recommendations,
                total_jobs_scanned=self._stats["jobs_collected"],
                platforms_searched=self._stats["platforms_searched"],
                platforms_failed=self._stats["platforms_failed"],
            )
        except Exception as e:
            print(f"[Supervisor] Email failed: {e}")
            return False

    # ================================================================
    # RUN LOG — Track pipeline execution
    # ================================================================

    def _create_run_log(self) -> int:
        """Create a new run log entry and return its ID."""
        db = get_db()
        try:
            run = RunLogModel(
                status="running",
                started_at=datetime.now(),
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            print(f"[Supervisor] Run #{run.id} started")
            return run.id
        finally:
            db.close()

    def _update_run_log(self, status: str, error_message: str = None) -> None:
        """Update the run log with final results."""
        db = get_db()
        try:
            run = db.query(RunLogModel).filter(RunLogModel.id == self._run_id).first()
            if run:
                run.status = status
                run.completed_at = datetime.now()
                run.jobs_collected = self._stats["jobs_collected"]
                run.jobs_new = self._stats["jobs_new"]
                run.jobs_matched = self._stats["jobs_matched"]
                run.recommendations_sent = self._stats["recommendations_sent"]
                run.collector_errors = self._stats["collector_errors"] or None
                run.error_message = error_message
                db.commit()
        except Exception as e:
            db.rollback()
            print(f"[Supervisor] Error updating run log: {e}")
        finally:
            db.close()

    def _print_summary(self) -> None:
        """Print a summary of the pipeline run."""
        print("\n" + "=" * 60)
        print("  SUPERVISOR — Pipeline Complete")
        print("=" * 60)
        print(f"  Jobs Collected:       {self._stats['jobs_collected']}")
        print(f"  Jobs New:             {self._stats['jobs_new']}")
        print(f"  Jobs Matched:         {self._stats['jobs_matched']}")
        print(f"  Recommendations Sent: {self._stats['recommendations_sent']}")
        print(f"  Platforms OK:         {', '.join(self._stats['platforms_searched']) or 'None'}")
        print(f"  Platforms Failed:     {', '.join(self._stats['platforms_failed']) or 'None'}")
        print("=" * 60)
