# ============================================================
# Memory Agent — Prevents Repeat Recommendations
# ============================================================
# PURPOSE:
#   Tracks what jobs have already been recommended so we don't
#   send the same job twice. Also tracks user feedback
#   (applied, not interested) to improve future recommendations.
#
# WHAT IT DOES:
#   1. Checks if a job was already recommended in a previous run
#   2. Checks if the user marked a job as "not interested"
#   3. Filters out both from today's recommendations
#   4. Records new recommendations for future reference
#
# DATA FLOW:
#   Ranking Agent produces 10 recommendations
#        │
#        ▼
#   [Memory Agent] checks recommendations table
#        │
#        ├─ Job #3 was recommended yesterday → REMOVE
#        ├─ Job #7 user marked "not interested" → REMOVE  
#        ├─ Jobs #1,2,4,5,6,8,9,10 → KEEP
#        │
#        ▼
#   8 recommendations go to email
# ============================================================

from datetime import datetime, timedelta
from typing import Optional
from database.connection import get_db
from database.models import RecommendationModel, JobPostingModel
from schemas.recommendation import Recommendation


class MemoryAgent:
    """
    Manages recommendation history and user feedback.
    
    Prevents the daily email from repeating the same jobs
    and learns from user actions over time.
    
    Usage:
        agent = MemoryAgent()
        filtered = agent.filter_seen(recommendations)
        agent.record_recommendations(filtered, run_id=1)
    """

    def __init__(self, lookback_days: int = 30):
        """
        Args:
            lookback_days: How many days to look back for previous recommendations.
                          Default 30 = don't re-recommend a job within 30 days.
        """
        self.lookback_days = lookback_days

    # ================================================================
    # MAIN METHOD — Filter out already-seen jobs
    # ================================================================

    def filter_seen(self, recommendations: list[Recommendation]) -> list[Recommendation]:
        """
        Remove jobs that were already recommended or rejected.
        
        Uses TWO dedup strategies:
        1. job_posting_id — matches by database ID
        2. job_url — catches duplicates even when IDs are None
        
        Args:
            recommendations: Today's candidate recommendations
        
        Returns:
            Filtered list with previously-seen jobs removed
        """
        if not recommendations:
            return []

        print(f"[Memory] Checking {len(recommendations)} recommendations against history...")

        # Get previously recommended job IDs and URLs
        seen_ids = self._get_previously_recommended_ids()
        rejected_ids = self._get_rejected_ids()
        seen_urls = self._get_previously_recommended_urls()

        all_excluded_ids = seen_ids | rejected_ids

        filtered = []
        removed_count = 0

        for rec in recommendations:
            # Check by ID OR by URL to catch all duplicates
            if rec.job_posting_id in all_excluded_ids:
                removed_count += 1
                print(f"  [Memory] Skipping (already seen by ID): {rec.title} @ {rec.company}")
            elif rec.job_url in seen_urls:
                removed_count += 1
                print(f"  [Memory] Skipping (already seen by URL): {rec.title} @ {rec.company}")
            else:
                filtered.append(rec)

        # Re-number rank positions
        for i, rec in enumerate(filtered):
            rec.rank_position = i + 1

        print(f"[Memory] Kept {len(filtered)}, removed {removed_count} "
              f"(seen IDs: {len(seen_ids)}, rejected: {len(rejected_ids)}, seen URLs: {len(seen_urls)})")

        return filtered

    # ================================================================
    # RECORD — Save today's recommendations for future reference
    # ================================================================

    def record_recommendations(
        self,
        recommendations: list[Recommendation],
        run_id: Optional[int] = None,
    ) -> None:
        """
        Save recommendations to the database so we can avoid
        repeating them in future runs.
        
        Args:
            recommendations: The final list that was sent in today's email
            run_id: The current pipeline run ID
        """
        db = get_db()
        try:
            for rec in recommendations:
                db_rec = RecommendationModel(
                    job_posting_id=rec.job_posting_id or 0,
                    match_score=rec.match_score,
                    rationale=rec.rationale,
                    missing_skills=rec.missing_skills,
                    rank_position=rec.rank_position,
                    run_id=run_id,
                    recommended_at=datetime.now(),
                )
                db.add(db_rec)

            db.commit()
            print(f"[Memory] Recorded {len(recommendations)} recommendations")
        except Exception as e:
            db.rollback()
            print(f"[Memory] Error recording: {e}")
        finally:
            db.close()

    # ================================================================
    # USER FEEDBACK — Track applied/not-interested actions
    # ================================================================

    def record_user_action(self, job_posting_id: int, action: str) -> None:
        """
        Record the user's action on a recommended job.
        
        Args:
            job_posting_id: ID of the job in our database
            action: "applied", "not_interested", or "saved"
        """
        db = get_db()
        try:
            # Update the job posting
            job = db.query(JobPostingModel).filter(
                JobPostingModel.id == job_posting_id
            ).first()
            if job:
                job.user_action = action

            # Update the recommendation
            rec = db.query(RecommendationModel).filter(
                RecommendationModel.job_posting_id == job_posting_id
            ).order_by(RecommendationModel.recommended_at.desc()).first()
            if rec:
                rec.user_action = action

            db.commit()
            print(f"[Memory] Recorded action '{action}' for job {job_posting_id}")
        except Exception as e:
            db.rollback()
            print(f"[Memory] Error recording action: {e}")
        finally:
            db.close()

    # ================================================================
    # QUERY METHODS
    # ================================================================

    def _get_previously_recommended_ids(self) -> set[int]:
        """Get IDs of jobs recommended in the last N days."""
        db = get_db()
        try:
            cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
            recs = db.query(RecommendationModel.job_posting_id).filter(
                RecommendationModel.recommended_at >= cutoff_date,
            ).all()
            return {r[0] for r in recs}
        finally:
            db.close()

    def _get_rejected_ids(self) -> set[int]:
        """Get IDs of jobs the user marked as 'not interested'."""
        db = get_db()
        try:
            jobs = db.query(JobPostingModel.id).filter(
                JobPostingModel.user_action == "not_interested",
            ).all()
            return {j[0] for j in jobs}
        finally:
            db.close()

    def _get_previously_recommended_urls(self) -> set[str]:
        """
        Get URLs of jobs recommended in the last N days.
        
        This catches duplicates even when job_posting_id is None,
        by joining the recommendations table with job_postings to
        look up the actual URL.
        """
        db = get_db()
        try:
            cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
            results = (
                db.query(JobPostingModel.url)
                .join(
                    RecommendationModel,
                    RecommendationModel.job_posting_id == JobPostingModel.id,
                )
                .filter(RecommendationModel.recommended_at >= cutoff_date)
                .all()
            )
            return {r[0] for r in results if r[0]}
        finally:
            db.close()

    def get_history_stats(self) -> dict:
        """Get statistics about recommendation history."""
        db = get_db()
        try:
            total_recs = db.query(RecommendationModel).count()
            applied = db.query(RecommendationModel).filter(
                RecommendationModel.user_action == "applied"
            ).count()
            rejected = db.query(RecommendationModel).filter(
                RecommendationModel.user_action == "not_interested"
            ).count()
            return {
                "total_recommendations": total_recs,
                "applied": applied,
                "not_interested": rejected,
                "no_action": total_recs - applied - rejected,
            }
        finally:
            db.close()
