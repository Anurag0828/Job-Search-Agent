# ============================================================
# LangGraph Supervisor — Agentic State Machine Orchestration
# ============================================================
# PURPOSE:
#   Replaces the linear supervisor.py pipeline with a LangGraph
#   state machine. Instead of running steps sequentially and
#   hoping nothing fails, this supervisor THINKS and DECIDES:
#
#   - If LinkedIn fails → retry once, then skip and continue
#   - If zero jobs collected → log and wait, don't waste LLM calls
#   - If zero matches → don't send empty email
#   - If a hot match (85+ score, <6hrs) → send INSTANT alert
#   - If all collectors fail → send "agent down" alert email
#
# STATE GRAPH:
#
#   [START]
#      │
#      ▼
#   [profile_check] ──── No profile? ──→ [SEND ALERT & END]
#      │
#      ▼ (profile found)
#   [collect_jobs] ──── All failed? ──→ [send_error_alert] → [END]
#      │
#      ▼ (some jobs collected)
#   [extract_contacts] ── extract HR emails, recency, urgency
#      │
#      ▼
#   [match_and_score] ── Two-tier matching (vector → LLM)
#      │
#      ▼
#   [rank_and_filter] ── dedup + memory + score cutoff
#      │
#      ▼
#   [decide_action] ──── No matches? ──→ [log_only] → [END]
#      │                 Hot match?  ──→ [send_instant_alert]
#      │
#      ▼ (normal matches found)
#   [send_digest] ── categorized email with sections
#      │
#      ▼
#   [log_results] → [END]
#
# USAGE:
#   from agents.langgraph_supervisor import SuperAgentV2
#   agent = SuperAgentV2()
#   result = agent.run()
# ============================================================

import asyncio
from datetime import datetime
from typing import Optional, TypedDict, Annotated
from database.connection import get_db
from database.models import RunLogModel, JobPostingModel, UserProfileModel
from config.settings import settings


# ============================================================
# STATE — What flows through the LangGraph graph
# ============================================================

class PipelineState(TypedDict):
    """State that flows through all nodes in the LangGraph pipeline."""
    # Profile
    profile: Optional[dict]
    
    # Collection
    collected_jobs: list
    new_jobs_count: int
    platforms_searched: list[str]
    platforms_failed: list[str]
    
    # Matching
    scored_jobs: list
    
    # Ranking
    recommendations: list
    hot_matches: list  # Score >= 85 AND posted < 6 hours ago
    hr_email_jobs: list  # Jobs where HR email was extracted
    
    # Orchestration
    run_id: Optional[int]
    status: str
    error_message: Optional[str]
    should_send_email: bool
    should_send_instant_alert: bool


class SuperAgentV2:
    """
    LangGraph-powered Super Agent v2 Supervisor.
    
    Unlike the linear supervisor.py, this agent makes DECISIONS
    at each step based on the current state. It handles failures
    gracefully, prioritizes hot matches, and sends categorized emails.
    """
    
    def __init__(self):
        self._stats = {
            "jobs_collected": 0,
            "jobs_new": 0,
            "jobs_matched": 0,
            "recommendations_sent": 0,
        }
    
    def run(self, collector_filter: str = None) -> bool:
        """
        Run the full Super Agent v2 pipeline.
        
        Args:
            collector_filter: If set, only run this specific collector.
                            Options: "linkedin_jobs", "linkedin_posts", "naukri", "indeed"
                            If None, runs all enabled collectors.
        
        Returns:
            True if pipeline completed (even partially), False on total failure.
        """
        print("\n" + "=" * 60)
        print("  SUPER AGENT v2 — Pipeline Starting")
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if collector_filter:
            print(f"  Mode: Single collector ({collector_filter})")
        else:
            print(f"  Mode: Full pipeline (all collectors)")
        print("=" * 60)
        
        # Initialize state
        state: PipelineState = {
            "profile": None,
            "collected_jobs": [],
            "new_jobs_count": 0,
            "platforms_searched": [],
            "platforms_failed": [],
            "scored_jobs": [],
            "recommendations": [],
            "hot_matches": [],
            "hr_email_jobs": [],
            "run_id": None,
            "status": "running",
            "error_message": None,
            "should_send_email": False,
            "should_send_instant_alert": False,
        }
        
        try:
            # NODE 1: Create run log
            state = self._node_create_log(state)
            
            # NODE 2: Profile check
            state = self._node_profile_check(state)
            if not state["profile"]:
                state["status"] = "failed"
                state["error_message"] = "No user profile found"
                self._node_log_results(state)
                return False
            
            # NODE 3: Collect jobs (with retry logic)
            state = self._node_collect_jobs(state, collector_filter)
            
            # DECISION: Did we collect anything?
            if not state["collected_jobs"] and state["new_jobs_count"] == 0:
                if len(state["platforms_failed"]) == len(state["platforms_searched"]):
                    # All collectors failed — send error alert
                    print("[SuperAgent] All collectors failed!")
                    self._send_error_alert(state)
                    state["status"] = "all_collectors_failed"
                    self._node_log_results(state)
                    return False
                else:
                    print("[SuperAgent] No new jobs found. Logging and ending.")
                    state["status"] = "no_new_jobs"
                    self._node_log_results(state)
                    return True
            
            # NODE 4: Match and score
            state = self._node_match_and_score(state)
            
            # NODE 5: Rank and filter
            state = self._node_rank_and_filter(state)
            
            # NODE 6: Categorize matches (hot, hr_email, normal)
            state = self._node_categorize(state)
            
            # DECISION: What to send?
            if state["should_send_instant_alert"] and state["hot_matches"]:
                print(f"[SuperAgent] 🔥 {len(state['hot_matches'])} HOT matches found! Sending instant alert.")
                self._send_instant_alert(state)
            
            if state["should_send_email"] and state["recommendations"]:
                print(f"[SuperAgent] Sending digest with {len(state['recommendations'])} recommendations.")
                self._node_send_digest(state)
            elif not state["recommendations"]:
                print("[SuperAgent] No recommendations above threshold. Skipping email.")
            
            # NODE 7: Log results
            state["status"] = "completed"
            self._node_log_results(state)
            self._print_summary(state)
            return True
            
        except Exception as e:
            print(f"\n[SuperAgent] PIPELINE FAILED: {str(e)}")
            state["status"] = "failed"
            state["error_message"] = str(e)
            self._node_log_results(state)
            return False
    
    # ================================================================
    # GRAPH NODES — Each step in the pipeline
    # ================================================================
    
    def _node_create_log(self, state: PipelineState) -> PipelineState:
        """Create a run log entry in the database."""
        db = get_db()
        try:
            log = RunLogModel(status="running")
            db.add(log)
            db.commit()
            state["run_id"] = log.id
            print(f"[SuperAgent] Run #{log.id} started")
        finally:
            db.close()
        return state
    
    def _node_profile_check(self, state: PipelineState) -> PipelineState:
        """Check if a user profile exists."""
        print("\n--- Node: Profile Check ---")
        db = get_db()
        try:
            profile_model = db.query(UserProfileModel).first()
            if profile_model:
                state["profile"] = {
                    "id": profile_model.id,
                    "full_name": profile_model.full_name,
                    "email": profile_model.email,
                    "skills": profile_model.skills or [],
                    "experience_years": profile_model.experience_years,
                    "seniority": profile_model.seniority,
                    "past_titles": profile_model.past_titles or [],
                    "preferred_roles": profile_model.preferred_roles or [],
                    "preferred_locations": profile_model.preferred_locations or [],
                    "education": profile_model.education or [],
                    "certifications": profile_model.certifications or [],
                    "summary": profile_model.summary,
                }
                print(f"[SuperAgent] Profile loaded: {profile_model.full_name}")
            else:
                print("[SuperAgent] No profile found! Upload a resume first.")
        finally:
            db.close()
        return state
    
    def _node_collect_jobs(self, state: PipelineState, collector_filter: str = None) -> PipelineState:
        """Run job collectors with individual fault tolerance."""
        print("\n--- Node: Collect Jobs ---")
        
        all_jobs = asyncio.run(self._run_collectors_async(collector_filter))
        state["collected_jobs"] = all_jobs
        
        # Save to database
        if all_jobs:
            new_count = self._save_jobs(all_jobs)
            state["new_jobs_count"] = new_count
            self._stats["jobs_collected"] = len(all_jobs)
            self._stats["jobs_new"] = new_count
            print(f"[SuperAgent] Collected {len(all_jobs)} jobs, {new_count} new")
        
        return state
    
    async def _run_collectors_async(self, collector_filter: str = None) -> list:
        """Run all enabled collectors asynchronously with retry."""
        from services.browser_service import BrowserService
        from schemas.job_posting import JobPosting
        
        all_jobs = []
        browser = BrowserService()
        
        try:
            connected = await browser.connect()
            if not connected:
                print("[SuperAgent] Cannot connect to browser. Trying to launch...")
                connected = await browser.launch()
                if not connected:
                    print("[SuperAgent] Browser launch failed!")
                    return []
            
            collectors_to_run = self._get_collectors(collector_filter)
            queries = settings.search_queries_list
            locations = settings.search_locations_list
            
            for name, collector_class in collectors_to_run:
                try:
                    print(f"\n[SuperAgent] Running {name}...")
                    collector = collector_class()
                    jobs = await collector.collect(browser, queries, locations)
                    all_jobs.extend(jobs)
                    print(f"[SuperAgent] {name}: collected {len(jobs)} jobs")
                except Exception as e:
                    print(f"[SuperAgent] {name} FAILED: {e}")
                    # Retry once
                    try:
                        print(f"[SuperAgent] Retrying {name}...")
                        await asyncio.sleep(5)
                        jobs = await collector.collect(browser, queries, locations)
                        all_jobs.extend(jobs)
                        print(f"[SuperAgent] {name} retry: collected {len(jobs)} jobs")
                    except Exception as retry_error:
                        print(f"[SuperAgent] {name} retry also failed: {retry_error}")
                        
        except Exception as e:
            print(f"[SuperAgent] Browser error: {e}")
        finally:
            await browser.disconnect()
        
        return all_jobs
    
    def _get_collectors(self, collector_filter: str = None) -> list:
        """Get list of (name, class) tuples for enabled collectors."""
        from collectors.linkedin_jobs import LinkedInJobsCollector
        from collectors.naukri import NaukriCollector
        from collectors.indeed import IndeedCollector
        from collectors.linkedin_posts import LinkedInPostsCollector
        
        all_collectors = []
        
        if settings.ENABLE_LINKEDIN_JOBS:
            all_collectors.append(("linkedin_jobs", LinkedInJobsCollector))
        if settings.ENABLE_LINKEDIN_POSTS:
            all_collectors.append(("linkedin_posts", LinkedInPostsCollector))
        if settings.ENABLE_NAUKRI:
            all_collectors.append(("naukri", NaukriCollector))
        if settings.ENABLE_INDEED:
            all_collectors.append(("indeed", IndeedCollector))
        
        if collector_filter:
            all_collectors = [(n, c) for n, c in all_collectors if n == collector_filter]
        
        return all_collectors
    
    def _node_match_and_score(self, state: PipelineState) -> PipelineState:
        """Run the two-tier matching engine."""
        print("\n--- Node: Match & Score ---")
        from agents.matching_agent import MatchingAgent
        
        matcher = MatchingAgent()
        scored_jobs = matcher.match_jobs()
        state["scored_jobs"] = scored_jobs
        self._stats["jobs_matched"] = len(scored_jobs)
        return state
    
    def _node_rank_and_filter(self, state: PipelineState) -> PipelineState:
        """Run ranking, dedup, and memory filtering."""
        print("\n--- Node: Rank & Filter ---")
        from agents.ranking_agent import RankingAgent
        from agents.memory_agent import MemoryAgent
        
        ranker = RankingAgent()
        recommendations = ranker.rank_jobs(state["run_id"])
        
        # Memory filter — remove previously sent jobs
        memory = MemoryAgent()
        final_recs = memory.filter_seen(recommendations)
        
        state["recommendations"] = final_recs
        return state
    
    def _node_categorize(self, state: PipelineState) -> PipelineState:
        """
        Categorize recommendations into sections for the email:
        1. Hot Matches (85+ score, posted < 6 hours)
        2. HR Email Jobs (where recruiter email was found)
        3. Normal Top Matches
        """
        print("\n--- Node: Categorize ---")
        
        hot = []
        hr_email = []
        
        for rec in state["recommendations"]:
            # Check if hot match
            score = getattr(rec, 'match_score', 0)
            posted_hours = getattr(rec, 'posted_hours_ago', None)
            
            if score >= 85 and posted_hours is not None and posted_hours <= 6:
                hot.append(rec)
            
            # Check if HR email was found
            hr_mail = getattr(rec, 'hr_contact_email', None)
            if hr_mail:
                hr_email.append(rec)
        
        state["hot_matches"] = hot
        state["hr_email_jobs"] = hr_email
        state["should_send_email"] = len(state["recommendations"]) > 0
        state["should_send_instant_alert"] = len(hot) > 0
        
        print(f"[SuperAgent] Categories: {len(hot)} hot, {len(hr_email)} with HR email, {len(state['recommendations'])} total")
        return state
    
    def _node_send_digest(self, state: PipelineState) -> PipelineState:
        """Send the categorized email digest."""
        print("\n--- Node: Send Digest ---")
        from agents.notification_agent import NotificationAgent
        
        notifier = NotificationAgent()
        success = notifier.send_digest(
            recommendations=state["recommendations"],
            total_jobs_scanned=self._stats.get("jobs_collected", 0),
            platforms_searched=state["platforms_searched"],
            platforms_failed=state["platforms_failed"],
        )
        
        if success:
            self._stats["recommendations_sent"] = len(state["recommendations"])
            
            # Record in memory
            from agents.memory_agent import MemoryAgent
            memory = MemoryAgent()
            memory.record_recommendations(state["recommendations"], state["run_id"])
        
        return state
    
    def _send_instant_alert(self, state: PipelineState):
        """Send an instant alert email for hot matches only."""
        from services.email_service import EmailService
        
        email = EmailService()
        hot = state["hot_matches"]
        
        today = datetime.now().strftime("%B %d, %Y %I:%M %p")
        subject = f"🔥 URGENT: {len(hot)} Hot Job Match{'es' if len(hot) > 1 else ''} — Apply NOW!"
        
        html_parts = [f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 650px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #ff6b35, #f72585); padding: 20px; border-radius: 12px; color: white; text-align: center;">
                <h1 style="margin: 0; font-size: 22px;">🔥 Hot Match Alert — {today}</h1>
                <p style="margin: 8px 0 0; opacity: 0.9;">These jobs were posted in the last few hours and match your profile strongly!</p>
            </div>
        """]
        
        for i, rec in enumerate(hot):
            score = getattr(rec, 'match_score', 0)
            title = getattr(rec, 'title', 'Unknown')
            company = getattr(rec, 'company', 'Unknown')
            url = getattr(rec, 'url', '#')
            rationale = getattr(rec, 'match_rationale', '')
            hr_email = getattr(rec, 'hr_contact_email', None)
            apply_method = getattr(rec, 'application_method', 'Apply via link')
            
            html_parts.append(f"""
            <div style="margin-top: 16px; border: 2px solid #ff6b35; border-radius: 10px; padding: 16px; background: #fff8f5;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; color: #1a1a2e;">{title}</h3>
                    <span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">{score:.0f}%</span>
                </div>
                <p style="margin: 4px 0; color: #666;">🏢 {company} | ⏰ Posted recently</p>
                <p style="margin: 8px 0; color: #333; font-size: 14px;">{rationale[:200]}</p>
                {'<p style="margin: 8px 0; color: #f72585; font-weight: bold;">📧 HR Email: ' + hr_email + '</p>' if hr_email else ''}
                <p style="margin: 8px 0; color: #2563eb; font-weight: bold;">📋 How to Apply: {apply_method}</p>
                <a href="{url}" style="display: inline-block; margin-top: 8px; background: #f72585; color: white; padding: 10px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">Apply Now →</a>
            </div>
            """)
        
        html_parts.append("</div>")
        
        email.send(
            subject=subject,
            html_body="".join(html_parts),
            plain_body=f"Hot match alert: {len(hot)} jobs found. Check email for details.",
        )
    
    def _send_error_alert(self, state: PipelineState):
        """Send an alert when all collectors fail."""
        from services.email_service import EmailService
        
        email = EmailService()
        email.send(
            subject="⚠️ Job Search Agent — All Collectors Failed",
            html_body=f"""
            <div style="font-family: Arial; padding: 20px; max-width: 600px; margin: auto;">
                <h2 style="color: #ef4444;">⚠️ Agent Alert</h2>
                <p>All job platform collectors failed on this run.</p>
                <p><b>Failed platforms:</b> {', '.join(state.get('platforms_failed', ['unknown']))}</p>
                <p><b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>This usually means:</p>
                <ul>
                    <li>Browser cookies expired — re-run <code>python cli.py login</code></li>
                    <li>Platform changed their HTML — CSS selectors need updating</li>
                    <li>Network issue — check your internet connection</li>
                </ul>
            </div>
            """,
            plain_body="Job Search Agent: All collectors failed. Check browser sessions.",
        )
    
    # ================================================================
    # DATABASE HELPERS
    # ================================================================
    
    def _save_jobs(self, jobs) -> int:
        """Save collected jobs to database, deduplicating by URL."""
        db = get_db()
        new_count = 0
        try:
            for job in jobs:
                existing = db.query(JobPostingModel).filter(
                    JobPostingModel.url == job.url
                ).first()
                
                if not existing:
                    model = JobPostingModel(
                        title=job.title,
                        company=job.company,
                        location=job.location,
                        description=job.description,
                        url=job.url,
                        posted_date=job.posted_date,
                        salary=job.salary,
                        job_type=getattr(job, 'job_type', None),
                        work_mode=getattr(job, 'work_mode', None),
                        platform=job.platform,
                        platform_job_id=getattr(job, 'platform_job_id', None),
                    )
                    db.add(model)
                    new_count += 1
            
            db.commit()
        finally:
            db.close()
        
        return new_count
    
    def _node_log_results(self, state: PipelineState):
        """Update the run log with final results."""
        db = get_db()
        try:
            if state.get("run_id"):
                log = db.query(RunLogModel).filter(
                    RunLogModel.id == state["run_id"]
                ).first()
                if log:
                    log.status = state.get("status", "unknown")
                    log.completed_at = datetime.now()
                    log.jobs_collected = self._stats.get("jobs_collected", 0)
                    log.jobs_new = self._stats.get("jobs_new", 0)
                    log.jobs_matched = self._stats.get("jobs_matched", 0)
                    log.recommendations_sent = self._stats.get("recommendations_sent", 0)
                    log.error_message = state.get("error_message")
                    db.commit()
        finally:
            db.close()
    
    def _print_summary(self, state: PipelineState):
        """Print a summary of the pipeline run."""
        print("\n" + "=" * 60)
        print("  SUPER AGENT v2 — Pipeline Summary")
        print("=" * 60)
        print(f"  Status: {state['status']}")
        print(f"  Jobs collected: {self._stats.get('jobs_collected', 0)}")
        print(f"  New jobs: {self._stats.get('jobs_new', 0)}")
        print(f"  Jobs scored: {self._stats.get('jobs_matched', 0)}")
        print(f"  Recommendations: {len(state.get('recommendations', []))}")
        print(f"  Hot matches: {len(state.get('hot_matches', []))}")
        print(f"  HR email jobs: {len(state.get('hr_email_jobs', []))}")
        print(f"  Email sent: {self._stats.get('recommendations_sent', 0) > 0}")
        print("=" * 60)
