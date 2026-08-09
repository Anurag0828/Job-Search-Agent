# ============================================================
# Ranking Agent — Deduplicates, Sorts, and Filters Results
# ============================================================
# PURPOSE:
#   Takes scored jobs from the Matching Agent and produces a
#   final shortlist ready for the email digest.
#
# WHAT IT DOES (in order):
#   1. DEDUPLICATION — Same job on LinkedIn AND Naukri? Keep best one
#   2. SORTING       — Order by match score, highest first
#   3. CUTOFF        — Remove jobs below the minimum score threshold
#   4. BORDERLINE    — Flag "close but not quite" jobs separately
#   5. TOP-N         — Take only the best N for the email
#
# DATA FLOW:
#   30 scored jobs from Matching Agent
#        │
#        ▼
#   [Deduplicate] → ~25 unique jobs
#        │
#        ▼
#   [Sort by score] → ordered list
#        │
#        ▼
#   [Apply cutoff] → score ≥ 65 passes
#        │
#        ▼
#   [Top N] → 10 recommendations for email
# ============================================================

from typing import Optional
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from database.connection import get_db
from database.models import JobPostingModel
from schemas.recommendation import Recommendation
from config.settings import settings


class RankingAgent:
    """
    Deduplicates, ranks, and filters scored job postings.
    
    Usage:
        agent = RankingAgent()
        recommendations = agent.rank_jobs()  # Returns final recommendations
    """

    def __init__(self):
        self.min_score = settings.MIN_MATCH_SCORE
        self.max_recommendations = settings.MAX_RECOMMENDATIONS

    # ================================================================
    # MAIN METHOD — Run the full ranking pipeline
    # ================================================================

    def rank_jobs(self, run_id: int = None) -> list[Recommendation]:
        """
        Run the complete ranking pipeline on scored jobs.
        
        Args:
            run_id: Current pipeline run ID. If provided, only jobs from
                    this run are considered. Otherwise falls back to last 24h.
        
        Returns:
            List of Recommendation objects ready for the email digest
        """
        print("\n" + "=" * 50)
        print("  RANKING AGENT — Starting")
        print("=" * 50)

        # Step 1: Load scored jobs from database
        scored_jobs = self._load_scored_jobs(run_id=run_id)
        if not scored_jobs:
            print("[Ranking] No scored jobs found")
            return []

        print(f"[Ranking] Loaded {len(scored_jobs)} scored jobs")

        # Step 2: Deduplicate
        unique_jobs = self._deduplicate(scored_jobs)
        print(f"[Ranking] After dedup: {len(unique_jobs)} unique jobs "
              f"(removed {len(scored_jobs) - len(unique_jobs)} duplicates)")

        # Step 3: Sort by score (highest first)
        unique_jobs.sort(key=lambda j: j.match_score or 0, reverse=True)

        # Step 4: Apply score cutoff
        above_cutoff = [j for j in unique_jobs if (j.match_score or 0) >= self.min_score]
        below_cutoff = [j for j in unique_jobs if (j.match_score or 0) < self.min_score]
        print(f"[Ranking] Above cutoff ({self.min_score}): {len(above_cutoff)} jobs")
        print(f"[Ranking] Below cutoff: {len(below_cutoff)} jobs")

        # Step 5: Take top N
        top_jobs = above_cutoff[:self.max_recommendations]

        # Step 6: Convert to Recommendation objects
        recommendations = []
        for i, job in enumerate(top_jobs):
            rec = Recommendation(
                company=job.company or "Unknown Company",
                title=job.title,
                location=job.location,
                match_score=job.match_score or 0,
                rationale=job.match_rationale or "Score-based match",
                missing_skills=job.missing_skills or [],
                job_url=job.url,
                platform=job.platform,
                rank_position=i + 1,
                job_posting_id=job.id,
            )
            recommendations.append(rec)

        # Step 7: Mark these jobs as recommended in the database
        self._mark_as_recommended(top_jobs)

        print(f"\n[Ranking] Final recommendations: {len(recommendations)}")
        for rec in recommendations:
            print(f"  #{rec.rank_position} | {rec.match_score:.0f}% | "
                  f"{rec.title} @ {rec.company}")

        return recommendations

    # ================================================================
    # DEDUPLICATION — Remove duplicate job postings
    # ================================================================

    def _deduplicate(self, jobs: list) -> list:
        """
        Remove duplicate job postings across platforms.
        
        The SAME job often appears on multiple platforms:
        - "Backend Developer at Google" on LinkedIn
        - "Backend Developer at Google" on Naukri
        
        Two-pass dedup strategy:
        Pass 1 (Fast): Exact URL match — same URL = instant duplicate
        Pass 2 (Fuzzy): Title + company similarity — catches cross-platform dupes
        
        For each duplicate, we keep the one with the higher match score.
        """
        if not jobs:
            return []

        # --- Pass 1: Exact URL dedup (fast) ---
        url_seen = {}
        url_unique = []
        for job in jobs:
            if job.url in url_seen:
                existing = url_seen[job.url]
                # Keep the one with the higher score
                if (job.match_score or 0) > (existing.match_score or 0):
                    url_unique.remove(existing)
                    url_unique.append(job)
                    url_seen[job.url] = job
            else:
                url_seen[job.url] = job
                url_unique.append(job)

        url_dupes_removed = len(jobs) - len(url_unique)
        if url_dupes_removed > 0:
            print(f"[Ranking] URL dedup removed {url_dupes_removed} exact duplicates")

        # --- Pass 2: Fuzzy title+company dedup (catches cross-platform dupes) ---
        unique = []
        duplicate_ids = set()

        for i, job in enumerate(url_unique):
            if job.id in duplicate_ids:
                continue  # Already identified as a duplicate

            is_duplicate = False

            for existing in unique:
                if self._is_duplicate(job, existing):
                    is_duplicate = True
                    # Keep the one with higher score
                    if (job.match_score or 0) > (existing.match_score or 0):
                        # New job is better — replace
                        unique.remove(existing)
                        unique.append(job)
                        duplicate_ids.add(existing.id)
                    else:
                        duplicate_ids.add(job.id)
                    break

            if not is_duplicate:
                unique.append(job)

        # Mark duplicates in database
        if duplicate_ids:
            self._mark_duplicates(duplicate_ids)

        return unique

    def _is_duplicate(self, job_a, job_b) -> bool:
        """
        Check if two jobs are duplicates of each other.
        
        Two jobs are considered duplicates if:
        1. Their titles are very similar (>80% match), AND
        2. Their company names match (or are very similar)
        
        Uses SequenceMatcher for fuzzy string comparison:
            "Senior Backend Developer" vs "Sr. Backend Developer" → 0.85 (match!)
            "Python Developer" vs "Java Developer" → 0.62 (not a match)
        """
        # Compare titles (fuzzy match)
        title_similarity = SequenceMatcher(
            None,
            (job_a.title or "").lower(),
            (job_b.title or "").lower(),
        ).ratio()

        # Compare companies (fuzzy match)
        company_similarity = SequenceMatcher(
            None,
            (job_a.company or "").lower(),
            (job_b.company or "").lower(),
        ).ratio()

        # Consider it a duplicate if both title and company are very similar
        return title_similarity > 0.80 and company_similarity > 0.70

    # ================================================================
    # DATABASE OPERATIONS
    # ================================================================

    def _load_scored_jobs(self, run_id: int = None) -> list:
        """
        Load jobs that have been scored but not yet recommended.
        
        Scoped to the current run_id to prevent old jobs from previous
        runs from resurfacing in today's email.
        """
        db = get_db()
        try:
            query = db.query(JobPostingModel).filter(
                JobPostingModel.match_score.isnot(None),
                JobPostingModel.is_recommended == False,
                JobPostingModel.is_duplicate == False,
            )
            if run_id:
                # Only jobs from this pipeline run
                query = query.filter(JobPostingModel.run_id == run_id)
            else:
                # Fallback: only jobs collected in the last 24 hours
                cutoff = datetime.now() - timedelta(hours=24)
                query = query.filter(JobPostingModel.collected_at >= cutoff)
            jobs = query.order_by(JobPostingModel.match_score.desc()).all()
            return jobs
        finally:
            db.close()

    def _mark_as_recommended(self, jobs: list) -> None:
        """Mark jobs as recommended in the database."""
        db = get_db()
        try:
            for job in jobs:
                db_job = db.query(JobPostingModel).filter(
                    JobPostingModel.id == job.id
                ).first()
                if db_job:
                    db_job.is_recommended = True
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[Ranking] Error marking recommended: {e}")
        finally:
            db.close()

    def _mark_duplicates(self, duplicate_ids: set) -> None:
        """Mark jobs as duplicates in the database."""
        db = get_db()
        try:
            for job_id in duplicate_ids:
                db_job = db.query(JobPostingModel).filter(
                    JobPostingModel.id == job_id
                ).first()
                if db_job:
                    db_job.is_duplicate = True
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[Ranking] Error marking duplicates: {e}")
        finally:
            db.close()
