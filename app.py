"""
frontend/app.py
Streamlit UI for the Job Assistant system.
Run: streamlit run frontend/app.py
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path
from typing import Optional

import httpx
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Assistant AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── API base URL ──────────────────────────────────────────────────────────────
API_URL = "http://localhost:8000"

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Main background */
  .stApp { background: #f0f4f8; }

  /* Sidebar */
  section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a365d 0%, #2b6cb0 100%);
  }
  section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
  section[data-testid="stSidebar"] input,
  section[data-testid="stSidebar"] select,
  section[data-testid="stSidebar"] textarea {
    background: rgba(255,255,255,0.12) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    border-radius: 6px !important;
  }

  /* Cards */
  .job-card {
    background: white;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    border-left: 4px solid #2b6cb0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    transition: transform .15s;
  }
  .job-card:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,0,0,0.12); }

  .score-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 14px;
  }
  .score-high  { background: #c6f6d5; color: #276749; }
  .score-med   { background: #fefcbf; color: #744210; }
  .score-low   { background: #fed7d7; color: #742a2a; }

  .tag {
    display: inline-block;
    background: #ebf8ff;
    color: #2b6cb0;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
    margin: 2px;
  }
  .tag-missing {
    background: #fff5f5;
    color: #c53030;
  }

  /* Metric cards */
  .metric-card {
    background: white;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.07);
  }
  .metric-value { font-size: 2rem; font-weight: 800; color: #2b6cb0; }
  .metric-label { font-size: 0.8rem; color: #718096; margin-top: 4px; }

  /* Buttons */
  div.stButton > button {
    background: linear-gradient(135deg, #2b6cb0, #1a365d);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 10px 24px;
    width: 100%;
  }
  div.stButton > button:hover {
    background: linear-gradient(135deg, #1a365d, #2b6cb0);
    transform: translateY(-1px);
  }

  h1 { color: #1a365d; }
  h2, h3 { color: #2d3748; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def score_class(score: float) -> str:
    if score >= 80:
        return "score-high"
    if score >= 60:
        return "score-med"
    return "score-low"


def call_api(method: str, path: str, **kwargs) -> dict | None:
    try:
        resp = httpx.request(method, f"{API_URL}{path}", timeout=120, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        st.error("❌ Cannot connect to backend. Start the API server first:\n`uvicorn backend.main:app --reload`")
        return None
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text[:300]}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None


def render_skill_tags(skills: list, cls: str = "tag") -> str:
    return " ".join(f'<span class="{cls}">{s}</span>' for s in skills[:10])


# ── Session state ─────────────────────────────────────────────────────────────
for key in ["user_id", "jobs", "selected_job", "generated"]:
    if key not in st.session_state:
        st.session_state[key] = None

if "jobs" not in st.session_state or st.session_state.jobs is None:
    st.session_state.jobs = []


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("# 🚀 Job Assistant AI")
    st.markdown("*Powered by Claude + Smart Matching*")
    st.divider()

    # ── Step 1: Upload Resume ─────────────────────────────────────────────────
    st.markdown("### 📄 Step 1: Upload Your Resume")
    uploaded_file = st.file_uploader(
        "PDF or DOCX",
        type=["pdf", "docx", "txt"],
        help="Your base resume. AI will tailor it for each job.",
    )
    col_name, col_email = st.columns(2)
    with col_name:
        user_name = st.text_input("Your Name", placeholder="Jane Doe")
    with col_email:
        user_email = st.text_input("Email", placeholder="jane@email.com")

    if uploaded_file and st.button("📤 Upload Resume"):
        with st.spinner("Parsing resume..."):
            resp = call_api(
                "POST", "/api/upload-resume",
                files={"file": (uploaded_file.name, uploaded_file.getvalue())},
                data={"name": user_name, "email": user_email},
            )
        if resp:
            st.session_state.user_id = resp["user_id"]
            st.success(f"✅ Resume uploaded! ({resp['char_count']} chars extracted)")

    if st.session_state.user_id:
        st.info(f"✅ Profile active (ID: `{st.session_state.user_id[:8]}...`)")

    st.divider()

    # ── Step 2: Job Preferences ───────────────────────────────────────────────
    st.markdown("### 🔍 Step 2: Job Preferences")
    keywords = st.text_input("Keywords", placeholder="Python Developer, ML Engineer")
    location = st.text_input("Location", placeholder="Hyderabad, India")
    exp_level = st.selectbox(
        "Experience Level",
        ["", "entry", "mid", "senior"],
        format_func=lambda x: x.capitalize() if x else "Any",
    )
    sources = st.multiselect(
        "Job Sources",
        ["linkedin", "indeed", "naukri"],
        default=["linkedin", "indeed", "naukri"],
    )
    results_per_source = st.slider("Results per source", 5, 30, 15)
    threshold = st.slider("Min Match Score (%)", 40, 90, 65)
    use_ai = st.toggle("AI-powered matching", value=True,
                       help="Uses Claude for smarter job scoring. Slower but more accurate.")

    search_clicked = st.button("🔍 Find Jobs & Match", disabled=not keywords)

    st.divider()
    st.markdown("### ⚙️ Settings")
    api_url_input = st.text_input("API URL", value=API_URL)
    if api_url_input != API_URL:
        API_URL = api_url_input


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("# 🚀 Job Assistant AI")
st.markdown("*Find jobs, get matched, generate ATS-optimised resumes — all in one click.*")

# ── Search ────────────────────────────────────────────────────────────────────
if search_clicked:
    if not keywords:
        st.warning("Please enter job keywords.")
    else:
        with st.spinner(f"🔍 Scraping {', '.join(sources)}... this may take 30–60 seconds."):
            payload = {
                "keywords": keywords,
                "location": location,
                "experience_level": exp_level,
                "sources": sources,
                "results_per_source": results_per_source,
                "user_id": st.session_state.user_id,
                "use_ai_matching": use_ai,
            }
            resp = call_api("POST", "/api/search-jobs", json=payload)

        if resp:
            st.session_state.jobs = resp.get("jobs", [])
            st.success(
                f"✅ Found **{resp['total']}** relevant jobs "
                f"from {resp['scraped']} scraped (threshold: {resp['threshold_used']}%)"
            )


# ── Metrics Row ───────────────────────────────────────────────────────────────
jobs = st.session_state.jobs or []
if jobs:
    col1, col2, col3, col4 = st.columns(4)
    avg_score = sum(j.get("match_score", 0) for j in jobs) / len(jobs)
    high_matches = sum(1 for j in jobs if j.get("match_score", 0) >= 80)
    sources_found = len(set(j.get("source", "") for j in jobs))

    for col, val, label in [
        (col1, len(jobs), "Jobs Matched"),
        (col2, f"{avg_score:.0f}%", "Avg Match Score"),
        (col3, high_matches, "Strong Matches (≥80%)"),
        (col4, sources_found, "Sources"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
              <div class="metric-value">{val}</div>
              <div class="metric-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")


# ── Job Listings ──────────────────────────────────────────────────────────────
if not jobs:
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color: #718096;">
      <h2>👆 Upload your resume and search for jobs to get started</h2>
      <p>The AI will match jobs to your profile and generate tailored resumes for each one.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"## 📋 Matched Jobs ({len(jobs)})")

    # Sort options
    sort_by = st.selectbox(
        "Sort by", ["Match Score ↓", "Company A-Z", "Source"],
        label_visibility="collapsed"
    )
    if sort_by == "Match Score ↓":
        jobs = sorted(jobs, key=lambda x: x.get("match_score", 0), reverse=True)
    elif sort_by == "Company A-Z":
        jobs = sorted(jobs, key=lambda x: x.get("company", ""))
    elif sort_by == "Source":
        jobs = sorted(jobs, key=lambda x: x.get("source", ""))

    for i, job in enumerate(jobs):
        score = job.get("match_score", 0)
        sc = score_class(score)
        matched_tags = render_skill_tags(job.get("matched_skills", []), "tag")
        missing_tags = render_skill_tags(job.get("missing_skills", []), "tag tag-missing")

        with st.container():
            st.markdown(f"""
            <div class="job-card">
              <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                  <h3 style="margin:0; color:#1a365d;">{job['title']}</h3>
                  <p style="margin:4px 0; color:#4a5568; font-size:15px;">
                    🏢 <b>{job['company']}</b> &nbsp;·&nbsp; 📍 {job.get('location','–')}
                    &nbsp;·&nbsp; 🌐 {job.get('source','').title()}
                  </p>
                  {f'<p style="color:#718096;font-size:12px;">💰 {job["salary_range"]}</p>' if job.get('salary_range') else ''}
                </div>
                <span class="score-badge {sc}">{score:.0f}% Match</span>
              </div>
              <div style="margin-top:8px;">
                <span style="font-size:12px; color:#276749;">✅ Matched: </span>{matched_tags}
              </div>
              <div style="margin-top:4px;">
                <span style="font-size:12px; color:#c53030;">⚠️ Gaps: </span>{missing_tags}
              </div>
              <p style="margin-top:8px; font-size:13px; color:#4a5568; line-height:1.5;">
                {job.get('description','')[:280]}...
              </p>
            </div>
            """, unsafe_allow_html=True)

            col_apply, col_gen, col_view = st.columns([1, 2, 1])
            with col_apply:
                if job.get("job_url"):
                    st.link_button("🔗 Apply", job["job_url"])
            with col_gen:
                btn_key = f"gen_{i}"
                if st.button(f"⚡ Generate Resume", key=btn_key,
                             disabled=not st.session_state.user_id):
                    if not st.session_state.user_id:
                        st.warning("Upload your resume first!")
                    else:
                        st.session_state.selected_job = job

            with col_view:
                with st.expander("📄 Full JD"):
                    st.write(job.get("description", "No description available."))


# ── Generate Resume Panel ─────────────────────────────────────────────────────
if st.session_state.selected_job:
    job = st.session_state.selected_job
    st.markdown("---")
    st.markdown(f"## ✍️ Generating Resume for: *{job['title']}* at *{job['company']}*")

    with st.spinner("🤖 Claude is rewriting your resume... (~30–60 sec)"):
        payload = {
            "user_id": st.session_state.user_id,
            "job_id": job.get("job_id", ""),
            "include_cover_letter": True,
        }
        resp = call_api("POST", "/api/generate-resume", json=payload)

    if resp:
        st.session_state.generated = resp
        st.session_state.selected_job = None  # reset trigger

        st.success(f"✅ Resume generated! ATS Score: **{resp['ats_score']:.0f}%**")

        gen = st.session_state.generated

        # ── ATS Report ────────────────────────────────────────────────────────
        ats_col1, ats_col2, ats_col3 = st.columns(3)
        with ats_col1:
            st.metric("ATS Score", f"{gen['ats_score']:.0f}%")
        with ats_col2:
            gaps = gen.get("keyword_gaps", [])
            st.metric("Keyword Gaps", len(gaps))
        with ats_col3:
            skills_req = gen.get("jd_analysis", {}).get("required_skills", [])
            st.metric("Required Skills in JD", len(skills_req))

        if gaps:
            st.warning(f"**Keyword Gaps:** {', '.join(gaps[:8])}")

        # ── Downloads ─────────────────────────────────────────────────────────
        st.markdown("### 📥 Download Your Tailored Resume")
        dl_col1, dl_col2, dl_col3 = st.columns(3)
        gen_id = gen.get("generated_id", "")

        with dl_col1:
            st.link_button(
                "📄 Download PDF", f"{API_URL}/api/download/pdf/{gen_id}",
                use_container_width=True
            )
        with dl_col2:
            st.link_button(
                "📝 Download DOCX", f"{API_URL}/api/download/docx/{gen_id}",
                use_container_width=True
            )
        with dl_col3:
            if gen.get("downloads", {}).get("cover_letter"):
                st.link_button(
                    "💌 Cover Letter", f"{API_URL}/api/download/cover-letter/{gen_id}",
                    use_container_width=True
                )

        # ── Resume Preview ────────────────────────────────────────────────────
        with st.expander("👁️ Preview Tailored Resume", expanded=True):
            resume = gen.get("resume_preview", {})
            if isinstance(resume, str):
                st.text(resume)
            else:
                st.markdown(f"### {resume.get('name', '')}")
                st.caption(
                    " | ".join(filter(None, [
                        resume.get("email"), resume.get("phone"),
                        resume.get("location"), resume.get("linkedin"),
                    ]))
                )
                st.markdown("**Summary:**")
                st.info(resume.get("summary", ""))

                skills = resume.get("skills", {})
                if skills.get("primary"):
                    st.markdown(f"**Core Skills:** {', '.join(skills['primary'])}")
                if skills.get("secondary"):
                    st.markdown(f"**Additional:** {', '.join(skills['secondary'])}")

                st.markdown("**Experience:**")
                for exp in resume.get("experience", []):
                    st.markdown(
                        f"**{exp.get('title')}** @ {exp.get('company')} "
                        f"({exp.get('start_date')} – {exp.get('end_date')})"
                    )
                    for b in exp.get("bullets", []):
                        st.markdown(f"  - {b}")

        # ── Cover Letter Preview ──────────────────────────────────────────────
        if gen.get("cover_letter"):
            with st.expander("💌 Cover Letter Preview"):
                st.text(gen["cover_letter"])

    else:
        st.session_state.selected_job = None  # reset on failure


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#a0aec0; font-size:12px;'>"
    "Job Assistant AI · Powered by Claude · Built with FastAPI + Streamlit"
    "</p>",
    unsafe_allow_html=True,
)
