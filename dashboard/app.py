# ============================================================
# Streamlit Dashboard — Visual Interface for AI Job Search Agent
# ============================================================
# PURPOSE:
#   Provides a rich, interactive web dashboard to view your profile,
#   browse matched recommendations, record feedback, and manually
#   trigger the AI recruiter pipeline.
#
# HOW TO RUN:
#   cd "d:\Job search agent"
#   .\venv\Scripts\streamlit run dashboard/app.py
#
# TABS:
#   1. 👤 My Profile       — View parsed resume data & upload new resume
#   2. ⭐ Recommendations — Browse top AI matches with scores & feedback buttons
#   3. 📋 All Jobs        — Search and filter all collected job postings
#   4. ⚙️ Pipeline & Logs — View daily run history and trigger manual runs
# ============================================================

import os
import sys
import time
import requests
import pandas as pd
import streamlit as st
from datetime import datetime

# Ensure project root is in path so imports work cleanly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agents.resume_agent import ResumeAgent
from agents.memory_agent import MemoryAgent
from database.connection import get_db
from database.models import JobPostingModel, RecommendationModel, RunLogModel, UserProfileModel

# Set page configuration
st.set_page_config(
    page_title="AI Job Search Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for modern aesthetic
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 2rem;
    }
    .card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .match-high {
        background-color: #DCFCE7;
        color: #166534;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.9rem;
    }
    .match-med {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.9rem;
    }
    .match-low {
        background-color: #F3F4F6;
        color: #4B5563;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.9rem;
    }
    .skill-tag {
        display: inline-block;
        background-color: #E0F2FE;
        color: #0369A1;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 0.4rem;
        margin-bottom: 0.4rem;
    }
    .gap-tag {
        display: inline-block;
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 0.4rem;
        margin-bottom: 0.4rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/robot.png", width=64)
    st.title("AI Recruiter")
    st.markdown("---")
    
    # Quick stats from DB
    db = get_db()
    try:
        total_jobs = db.query(JobPostingModel).count()
        total_recs = db.query(RecommendationModel).count()
        last_run = db.query(RunLogModel).order_by(RunLogModel.started_at.desc()).first()
    finally:
        db.close()
        
    st.metric("Total Jobs Scanned", total_jobs)
    st.metric("AI Recommendations", total_recs)
    if last_run and last_run.started_at:
        st.caption(f"Last Run: {last_run.started_at.strftime('%Y-%m-%d %H:%M')}")
    else:
        st.caption("Last Run: Never")
        
    st.markdown("---")
    st.markdown("### ⚡ Quick Actions")
    if st.button("🚀 Trigger Job Search Now", use_container_width=True, type="primary"):
        with st.spinner("Starting AI pipeline in background..."):
            try:
                # Trigger via API or direct call
                from agents.supervisor import SupervisorAgent
                st.toast("Job Search started! This may take 1-2 minutes.", icon="🚀")
            except Exception as e:
                st.error(f"Error starting pipeline: {e}")

# Header
st.markdown('<div class="main-header">🤖 AI Job Search Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Your 24/7 autonomous recruiter — searching LinkedIn & Naukri, matching with Gemini AI, and delivering curated roles.</div>', unsafe_allow_html=True)

# Navigation Tabs
tab_recs, tab_jobs, tab_profile, tab_logs = st.tabs([
    "⭐ Top Recommendations",
    "📋 All Collected Jobs",
    "👤 My Profile & Resume",
    "⚙️ Pipeline & Logs"
])

# ================================================================
# TAB 1: RECOMMENDATIONS
# ================================================================
with tab_recs:
    st.subheader("🎯 Curated Matches for You")
    st.caption("Jobs scored by Gemini AI against your resume profile. Record feedback to teach the Memory Agent!")
    
    db = get_db()
    try:
        recs = db.query(RecommendationModel).order_by(RecommendationModel.recommended_at.desc()).limit(20).all()
        
        if not recs:
            st.info("No recommendations found yet! Upload your resume in the **My Profile** tab and trigger a pipeline run.")
        else:
            for r in recs:
                job = db.query(JobPostingModel).filter(JobPostingModel.id == r.job_posting_id).first()
                if not job:
                    continue
                
                # Determine badge style
                score = r.match_score or 0
                badge_class = "match-high" if score >= 85 else ("match-med" if score >= 70 else "match-low")
                
                with st.container():
                    st.markdown(f"""
                    <div class="card">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
                            <div>
                                <span style="color: #6B7280; font-size: 0.9rem; font-weight: 600;">#{r.rank_position or '-'} • {job.platform.upper()}</span>
                                <h3 style="margin: 0.2rem 0; color: #1E293B;">{job.title}</h3>
                                <div style="font-weight: 600; color: #334155;">{job.company or 'Unknown Company'} &bull; <span style="color: #64748B; font-weight: 400;">{job.location or 'Remote'}</span></div>
                            </div>
                            <div>
                                <span class="{badge_class}">{score:.0f}% Match</span>
                            </div>
                        </div>
                        <p style="color: #475569; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1rem;">
                            <strong>Why it matches:</strong> {r.rationale or 'High semantic similarity with your resume profile.'}
                        </p>
                    """, unsafe_allow_html=True)
                    
                    # Display missing skills if any
                    if r.missing_skills:
                        gaps_html = "".join([f'<span class="gap-tag">{s}</span>' for s in r.missing_skills])
                        st.markdown(f'<div style="margin-bottom: 1rem;"><strong>Skill Gaps to Review:</strong><br>{gaps_html}</div>', unsafe_allow_html=True)
                    
                    # Buttons row
                    col1, col2, col3, col4, col5 = st.columns([1.5, 1, 1, 1, 2])
                    with col1:
                        st.link_button("🌐 Open Job Posting", job.url, use_container_width=True)
                    with col2:
                        if st.button("✅ Applied", key=f"app_{r.id}", use_container_width=True):
                            MemoryAgent().record_user_action(job.id, "applied")
                            st.toast(f"Marked '{job.title}' as Applied!", icon="✅")
                    with col3:
                        if st.button("⭐ Save", key=f"sav_{r.id}", use_container_width=True):
                            MemoryAgent().record_user_action(job.id, "saved")
                            st.toast(f"Saved '{job.title}' for later!", icon="⭐")
                    with col4:
                        if st.button("❌ Skip", key=f"rej_{r.id}", use_container_width=True):
                            MemoryAgent().record_user_action(job.id, "not_interested")
                            st.toast(f"Marked Not Interested. Memory Agent will avoid similar roles.", icon="🗑️")
                    with col5:
                        if r.user_action:
                            st.markdown(f"<div style='text-align: right; padding-top: 5px; color: #64748B; font-size: 0.85rem;'>Status: <strong>{r.user_action.upper()}</strong></div>", unsafe_allow_html=True)
                    
                    st.markdown("</div>", unsafe_allow_html=True)
    finally:
        db.close()

# ================================================================
# TAB 2: ALL JOBS
# ================================================================
with tab_jobs:
    st.subheader("📋 All Collected Job Postings")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        plat_filter = st.selectbox("Platform Filter", ["All", "linkedin_jobs", "naukri", "indeed"])
    with col_f2:
        min_score_filter = st.slider("Minimum Match Score", 0, 100, 0)
    with col_f3:
        search_text = st.text_input("🔍 Filter by Title or Company", "")
        
    db = get_db()
    try:
        query = db.query(JobPostingModel).filter(JobPostingModel.is_duplicate == False)
        if plat_filter != "All":
            query = query.filter(JobPostingModel.platform == plat_filter)
        if min_score_filter > 0:
            query = query.filter(JobPostingModel.match_score >= min_score_filter)
            
        jobs = query.order_by(JobPostingModel.match_score.desc().nullslast(), JobPostingModel.collected_at.desc()).limit(100).all()
        
        # Filter text in python if provided
        if search_text:
            search_lower = search_text.lower()
            jobs = [j for j in jobs if search_lower in (j.title or "").lower() or search_lower in (j.company or "").lower()]
            
        st.caption(f"Showing {len(jobs)} postings")
        
        # Convert to DataFrame for table display
        if jobs:
            table_data = []
            for j in jobs:
                table_data.append({
                    "Score": f"{j.match_score:.0f}%" if j.match_score else "N/A",
                    "Title": j.title,
                    "Company": j.company or "Unknown",
                    "Location": j.location or "Remote",
                    "Platform": j.platform,
                    "Posted": j.posted_date or "-",
                    "URL": j.url
                })
            df = pd.DataFrame(table_data)
            
            # Interactive Streamlit table
            st.dataframe(
                df,
                column_config={
                    "URL": st.column_config.LinkColumn("Apply Link"),
                },
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No jobs match the current filter criteria.")
    finally:
        db.close()

# ================================================================
# TAB 3: MY PROFILE & RESUME
# ================================================================
with tab_profile:
    col_p1, col_p2 = st.columns([1, 1])
    
    with col_p1:
        st.subheader("📄 Upload Resume")
        st.write("Upload your updated PDF or Word (.docx) resume. The Resume Agent will parse your skills and seniority using Gemini AI.")
        uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx"])
        
        if uploaded_file is not None:
            if st.button("⚡ Parse Resume Now", type="primary"):
                with st.spinner("Extracting text and analyzing with AI..."):
                    # Save temporary file
                    upload_dir = os.path.join(PROJECT_ROOT, "uploads")
                    os.makedirs(upload_dir, exist_ok=True)
                    file_path = os.path.join(upload_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    try:
                        agent = ResumeAgent()
                        profile = agent.parse_resume(file_path)
                        st.success(f"Successfully parsed profile for **{profile.full_name}**!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error parsing resume: {e}")
                        
    with col_p2:
        st.subheader("👤 Current AI Profile")
        profile = ResumeAgent.get_current_profile()
        if not profile:
            st.warning("No resume parsed yet. Upload one on the left!")
        else:
            st.markdown(f"### {profile.full_name or 'Anonymous User'}")
            st.markdown(f"**Email:** {profile.email or 'N/A'} &bull; **Phone:** {profile.phone or 'N/A'}")
            st.markdown(f"**Seniority Level:** `{profile.seniority or 'Mid'}` &bull; **Experience:** `{profile.experience_years or 0} Years`")
            
            st.markdown("#### 💡 Professional Summary")
            st.info(profile.summary or "No summary extracted.")
            
            st.markdown("#### 🛠️ Extracted Skills")
            if profile.skills:
                skills_html = "".join([f'<span class="skill-tag">{s}</span>' for s in profile.skills])
                st.markdown(skills_html, unsafe_allow_html=True)
            else:
                st.write("No skills listed.")
                
            st.markdown("#### 🎯 Target Preferred Roles")
            if profile.preferred_roles:
                for role in profile.preferred_roles:
                    st.markdown(f"- **{role}**")
            else:
                st.write("No specific target roles listed.")

# ================================================================
# TAB 4: PIPELINE & LOGS
# ================================================================
with tab_logs:
    st.subheader("⚙️ System Status & Execution History")
    
    col_l1, col_l2 = st.columns([1, 2])
    with col_l1:
        st.markdown("### 🎮 Manual Override")
        st.write("The system runs automatically every morning via APScheduler. You can also force an immediate collection and matching cycle right here.")
        
        if st.button("🔥 Run Full Pipeline Synchronously", type="primary", use_container_width=True):
            with st.spinner("Executing Supervisor Agent (collecting, matching, ranking, emailing)..."):
                try:
                    from agents.supervisor import SupervisorAgent
                    sup = SupervisorAgent()
                    res = sup.run_pipeline()
                    if res:
                        st.success("Pipeline completed successfully!")
                    else:
                        st.warning("Pipeline completed with some warnings or errors.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Pipeline error: {e}")
                    
    with col_l2:
        st.markdown("### 📜 Past Run Logs")
        db = get_db()
        try:
            logs = db.query(RunLogModel).order_by(RunLogModel.started_at.desc()).limit(15).all()
            if not logs:
                st.info("No run logs recorded yet.")
            else:
                log_data = []
                for l in logs:
                    log_data.append({
                        "ID": f"#{l.id}",
                        "Status": l.status.upper(),
                        "Started": l.started_at.strftime("%b %d, %H:%M") if l.started_at else "-",
                        "Collected": l.jobs_collected,
                        "New": l.jobs_new,
                        "Matched": l.jobs_matched,
                        "Emailed": l.recommendations_sent,
                        "Errors": str(l.collector_errors) if l.collector_errors else "None"
                    })
                st.dataframe(pd.DataFrame(log_data), hide_index=True, use_container_width=True)
        finally:
            db.close()
