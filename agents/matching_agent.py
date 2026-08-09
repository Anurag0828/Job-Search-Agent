# ============================================================
# Matching Agent — Scores Jobs Against Your Profile
# ============================================================
# PURPOSE:
#   Takes collected jobs and scores each one against your profile.
#   Uses a TWO-LAYER approach for speed and intelligence:
#
#   Layer 1: VECTOR SEARCH (fast, free)
#     500 jobs → embed → compare vectors → top 30 candidates
#     Speed: seconds | Cost: $0 (local model)
#
#   Layer 2: LLM DEEP ANALYSIS (smart, detailed)
#     30 candidates → send to Gemini with your profile →
#     → score, rationale, missing skills
#     Speed: ~1 min | Cost: free with Gemini
#
# DATA FLOW:
#   job_postings table + user_profiles table
#        │
#        ▼
#   [Layer 1: Vector similarity — fast pre-filter]
#        │
#        ▼
#   Top 30 candidates
#        │
#        ▼
#   [Layer 2: LLM analysis — detailed scoring]
#        │
#        ▼
#   30 scored jobs with rationale + missing skills
#        │
#        ▼
#   Updated in job_postings table (match_score, match_rationale)
# ============================================================

from typing import Optional
from services.llm_service import get_llm
from services.embedding_service import get_embedder
from services.vector_store import get_vector_store
from database.connection import get_db
from database.models import JobPostingModel, UserProfileModel
from schemas.job_posting import JobPostingWithScore


class MatchingAgent:
    """
    Scores job postings against the user's profile.
    
    Two-layer matching strategy:
      Layer 1 (Vector): Fast, cheap, handles hundreds of jobs
      Layer 2 (LLM):    Smart, detailed, handles tens of jobs
    
    Usage:
        agent = MatchingAgent()
        scored_jobs = agent.match_jobs()  # Returns scored jobs
    """

    def __init__(self):
        self._llm = None
        self._embedder = None
        self._vector_store = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder

    @property
    def vector_store(self):
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    # ================================================================
    # MAIN METHOD — Run the full matching pipeline
    # ================================================================

    def match_jobs(self, top_k_vector: int = 30, top_k_final: int = 15) -> list[JobPostingWithScore]:
        """
        Run the complete two-layer matching pipeline.
        
        Args:
            top_k_vector: How many jobs to take from vector search (Layer 1)
            top_k_final: How many to keep after LLM scoring (Layer 2)
        
        Returns:
            List of JobPostingWithScore objects, sorted by score (highest first)
        """
        print("\n" + "=" * 50)
        print("  MATCHING AGENT — Starting")
        print("=" * 50)

        # Step 1: Load the user profile from the database
        profile = self._load_profile()
        if not profile:
            print("[Matching] No user profile found! Upload a resume first.")
            return []

        # Step 2: Load unmatched jobs from the database
        unmatched_jobs = self._load_unmatched_jobs()
        if not unmatched_jobs:
            print("[Matching] No new jobs to match")
            return []

        print(f"[Matching] Found {len(unmatched_jobs)} unmatched jobs")

        # Step 3: Layer 1 — Vector similarity (fast pre-filter)
        print(f"\n--- Layer 1: Vector Similarity ---")
        candidates = self._vector_match(profile, unmatched_jobs, top_k_vector)
        print(f"[Matching] Layer 1 selected {len(candidates)} candidates")

        # Step 4: Layer 2 — LLM deep analysis (detailed scoring)
        print(f"\n--- Layer 2: LLM Deep Analysis ---")
        scored_jobs = self._llm_match(profile, candidates)
        print(f"[Matching] Layer 2 scored {len(scored_jobs)} jobs")

        # Step 5: Sort by score (highest first)
        scored_jobs.sort(key=lambda j: j.match_score, reverse=True)

        # Step 6: Save scores to database
        self._save_scores(scored_jobs)

        print(f"\n[Matching] Complete! Top score: "
              f"{scored_jobs[0].match_score:.0f}/100" if scored_jobs else "")
        return scored_jobs

    # ================================================================
    # LAYER 1 — Vector Similarity (Fast Pre-Filter)
    # ================================================================

    def _vector_match(
        self,
        profile: dict,
        jobs: list[dict],
        top_k: int = 30,
    ) -> list[dict]:
        """
        Layer 1: Use vector similarity to quickly find the most relevant jobs.
        
        How it works:
        1. Convert the user's profile into an embedding vector
        2. Convert each job description into an embedding vector
        3. Find the top-K jobs with the highest cosine similarity
        
        This processes 500 jobs in seconds — much faster than sending
        all 500 to the LLM.
        """
        # Add all jobs to the vector store
        job_dicts = [
            {
                "title": j.get("title", ""),
                "company": j.get("company", ""),
                "location": j.get("location", ""),
                "description": j.get("description", ""),
                "url": j.get("url", ""),
                "platform": j.get("platform", ""),
            }
            for j in jobs
        ]
        self.vector_store.add_jobs(job_dicts)

        # Create profile text for embedding
        profile_text = self.embedder.create_profile_text(profile)

        # Search for similar jobs
        results = self.vector_store.find_similar(profile_text, top_k=top_k)

        # Map results back to full job data
        candidates = []
        result_urls = {r["url"] for r in results}
        for job in jobs:
            if job.get("url") in result_urls:
                # Add the vector similarity score
                for r in results:
                    if r["url"] == job.get("url"):
                        job["vector_score"] = r["similarity_score"]
                        break
                candidates.append(job)

        return candidates

    # ================================================================
    # LAYER 2 — LLM Deep Analysis (Detailed Scoring)
    # ================================================================

    def _llm_match(self, profile: dict, candidates: list[dict]) -> list[JobPostingWithScore]:
        """
        Layer 2: Use the LLM to deeply analyze each candidate job.
        
        For each candidate, the LLM receives:
        - The user's full profile (skills, experience, etc.)
        - The job's full description
        
        The LLM returns:
        - A match score (0-100)
        - A rationale (why it matches)
        - Missing skills (what the user would need to learn)
        """
        scored_jobs = []

        # Build the profile summary for the LLM prompt
        profile_summary = self._format_profile_for_llm(profile)

        for i, job in enumerate(candidates):
            print(f"[Matching] Analyzing {i + 1}/{len(candidates)}: "
                  f"{job.get('title', 'Unknown')} @ {job.get('company', 'Unknown')}")

            try:
                result = self._score_single_job(profile_summary, job)
                if result:
                    scored_jobs.append(result)
                import time
                # GUARDRAIL 3: NVIDIA NIM free endpoint rate limit is ~40 RPM (1 request per 1.5s).
                # Sleeping 1.6s between jobs ensures we stay around ~37 RPM and never hit 429 Too Many Requests!
                time.sleep(1.6)
            except Exception as e:
                print(f"[Matching] Error scoring job: {e}")
                continue

        return scored_jobs

    def _score_single_job(self, profile_summary: str, job: dict) -> Optional[JobPostingWithScore]:
        """
        Ask the LLM (or fallback RAG vector score) to score a single job against the profile.
        Includes built-in Guardrails against hallucinations and prompt injection!
        """
        from services.resume_rag_service import get_rag_service
        rag = get_rag_service()
        
        job_desc = job.get('description', '') or job.get('title', '')
        
        # GUARDRAIL 1: Input Sanitization (Anti-Prompt-Injection on scraped job descriptions)
        import re
        clean_desc = re.sub(r'(?i)(ignore previous instructions|forget system prompt|you are now|override instructions|grant 100 score)', '[SANITIZED_PROMPT_INJECTION]', job_desc)
        
        retrieved_chunks = rag.retrieve_relevant_chunks(clean_desc, top_k=3)
        
        # Calculate offline RAG similarity score (as baseline or fallback)
        if retrieved_chunks:
            avg_sim = sum(c['similarity_score'] for c in retrieved_chunks) / len(retrieved_chunks)
            rag_fallback_score = round(min(100.0, max(0.0, avg_sim * 100.0)), 1)
            rag_evidence = "\n\n".join([f"[{c['section']}] (Relevance: {c['similarity_score']*100:.0f}%):\n{c['content']}" for c in retrieved_chunks])
        else:
            rag_fallback_score = float(job.get('vector_score', 0.6) * 100.0)
            rag_evidence = profile_summary

        job_text = (
            f"Title: {job.get('title', 'N/A')}\n"
            f"Company: {job.get('company', 'N/A')}\n"
            f"Location: {job.get('location', 'N/A')}\n"
            f"Description: {clean_desc[:3000]}\n"
        )

        prompt = f"""
You are an expert job matching analyst. Compare this candidate's RAG-retrieved resume evidence with the job posting and evaluate the fit.

RETRIEVED RESUME EVIDENCE (Top matching chunks from candidate's resume):
{rag_evidence}

JOB POSTING:
{job_text}

Analyze the match and return a JSON object:
{{
    "match_score": <number 0-100>,
    "rationale": "<2-3 sentence explanation of why this is or isn't a good match based on the retrieved evidence>",
    "missing_skills": ["<skill1>", "<skill2>"],
    "matching_skills": ["<skill1>", "<skill2>"],
    "fit_level": "<strong_match | good_match | moderate_match | weak_match | poor_match>"
}}

SCORING GUIDE:
- 90-100: Almost perfect match — skills, experience, and level all align
- 75-89:  Strong match — most skills align, minor gaps
- 60-74:  Good match — core skills match, some notable gaps
- 40-59:  Moderate match — some overlap but significant gaps
- 0-39:   Weak match — major misalignment in skills or experience

Be realistic. Most matches should be in the 50-80 range.
Return ONLY the JSON, no other text.
"""

        system_prompt = (
            "You are a precise job matching analyst using RAG evidence. "
            "Score matches accurately based on skill overlap and role alignment. "
            "Be realistic — don't inflate scores."
        )

        try:
            result = self.llm.call_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,
            )
            if result and "match_score" in result:
                match_score = float(result.get("match_score", rag_fallback_score))
                
                # GUARDRAIL 2: Score Hallucination Clamp (prevent LLM from over-inflating irrelevant jobs)
                if match_score - rag_fallback_score > 35.0:
                    print(f"[Matching Guardrail] Adjusted hallucinated score {match_score:.0f} -> RAG grounded score {(match_score + rag_fallback_score)/2:.0f}")
                    match_score = round((match_score + rag_fallback_score) / 2.0, 1)
                    
                rationale = result.get("rationale", f"RAG semantic similarity match ({match_score:.0f}%) with your profile.")
                missing_skills = result.get("missing_skills", [])
            else:
                raise ValueError("LLM returned empty score")
        except Exception as e:
            # Fallback to offline RAG vector similarity score!
            print(f"[Matching] Note: LLM scoring unavailable ({e}). Using offline RAG vector score ({rag_fallback_score}%).")
            match_score = rag_fallback_score
            rationale = f"Offline RAG vector similarity match ({match_score:.0f}%) based on top retrieved sections from your resume."
            missing_skills = []

        return JobPostingWithScore(
            title=job.get("title", ""),
            company=job.get("company"),
            location=job.get("location"),
            description=job.get("description"),
            url=job.get("url", ""),
            platform=job.get("platform", ""),
            posted_date=job.get("posted_date"),
            salary=job.get("salary"),
            platform_job_id=job.get("platform_job_id"),
            match_score=match_score,
            match_rationale=rationale,
            missing_skills=missing_skills,
        )

    # ================================================================
    # HELPER METHODS
    # ================================================================

    def _load_profile(self) -> Optional[dict]:
        """Load the user profile from the database."""
        db = get_db()
        try:
            profile = db.query(UserProfileModel).first()
            if not profile:
                return None
            return {
                "full_name": profile.full_name,
                "skills": profile.skills or [],
                "experience_years": profile.experience_years,
                "seniority": profile.seniority,
                "preferred_roles": profile.preferred_roles or [],
                "preferred_locations": profile.preferred_locations or [],
                "education": profile.education or [],
                "certifications": profile.certifications or [],
                "summary": profile.summary,
            }
        finally:
            db.close()

    def _load_unmatched_jobs(self) -> list[dict]:
        """Load jobs that haven't been matched yet."""
        db = get_db()
        try:
            jobs = db.query(JobPostingModel).filter(
                JobPostingModel.match_score.is_(None)
            ).all()
            return [
                {
                    "id": j.id,
                    "title": j.title,
                    "company": j.company,
                    "location": j.location,
                    "description": j.description,
                    "url": j.url,
                    "platform": j.platform,
                    "posted_date": j.posted_date,
                    "salary": j.salary,
                    "platform_job_id": j.platform_job_id,
                }
                for j in jobs
            ]
        finally:
            db.close()

    def _format_profile_for_llm(self, profile: dict) -> str:
        """Format the user profile as readable text for the LLM prompt."""
        parts = [f"Name: {profile.get('full_name', 'N/A')}"]
        if profile.get("seniority"):
            parts.append(f"Level: {profile['seniority']}")
        if profile.get("experience_years"):
            parts.append(f"Experience: {profile['experience_years']} years")
        if profile.get("skills"):
            parts.append(f"Skills: {', '.join(profile['skills'])}")
        if profile.get("preferred_roles"):
            parts.append(f"Target roles: {', '.join(profile['preferred_roles'])}")
        if profile.get("summary"):
            parts.append(f"Summary: {profile['summary']}")
        return "\n".join(parts)

    def _save_scores(self, scored_jobs: list[JobPostingWithScore]) -> None:
        """Save match scores back to the database."""
        db = get_db()
        try:
            for job in scored_jobs:
                db_job = db.query(JobPostingModel).filter(
                    JobPostingModel.url == job.url
                ).first()
                if db_job:
                    db_job.match_score = job.match_score
                    db_job.match_rationale = job.match_rationale
                    db_job.missing_skills = job.missing_skills
            db.commit()
            print(f"[Matching] Saved {len(scored_jobs)} scores to database")
        except Exception as e:
            db.rollback()
            print(f"[Matching] Error saving scores: {e}")
        finally:
            db.close()
