"""
backend/resume_generator.py
Rewrites the user's base resume to be ATS-optimised for a specific JD.
Uses Claude to:
  1. Parse the JD → extract skills / keywords / responsibilities
  2. Rewrite resume sections using action verbs, JD keywords, ATS formatting
  3. Produce a structured resume dict ready for PDF/DOCX rendering
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import anthropic

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── System prompts ────────────────────────────────────────────────────────────
_JD_PARSER_SYSTEM = """You are an expert recruiter and ATS specialist.
Parse the job description and return ONLY a JSON object:
{
  "required_skills": ["skill1", "skill2"],
  "preferred_skills": ["skill3"],
  "responsibilities": ["resp1", "resp2"],
  "experience_years": "3-5",
  "education": "Bachelor's in CS or related",
  "key_keywords": ["keyword1", "keyword2"],
  "seniority": "mid-level",
  "role_summary": "One sentence describing the role"
}
Return ONLY JSON. No markdown, no extra text."""


_RESUME_REWRITER_SYSTEM = """You are a senior resume writer and ATS optimization expert.
Your task is to rewrite a candidate's resume to be perfectly tailored for a specific job.

STRICT RULES:
1. NEVER fabricate experience, projects, or skills the candidate doesn't have.
2. USE keywords from the JD naturally throughout the resume.
3. START every bullet point with a strong action verb (Developed, Architected, Led, etc.)
4. QUANTIFY achievements where possible (even estimates like "~20% faster").
5. FORMAT for ATS: no tables, no columns, no headers/footers in body, plain sections.
6. KEEP the candidate's actual timeline and companies exactly as provided.
7. TAILOR the professional summary to the specific role.
8. REORDER skills to put JD-relevant skills first.

Return ONLY a JSON object with this structure:
{
  "name": "Full Name",
  "email": "email@example.com",
  "phone": "+1-xxx-xxx-xxxx",
  "linkedin": "linkedin.com/in/handle",
  "github": "github.com/handle",
  "location": "City, State",
  "summary": "3-4 sentence tailored professional summary",
  "skills": {
    "primary": ["skill1", "skill2"],
    "secondary": ["skill3", "skill4"]
  },
  "experience": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "location": "City, ST",
      "start_date": "Jan 2022",
      "end_date": "Present",
      "bullets": [
        "Action verb + what you did + measurable outcome",
        "..."
      ]
    }
  ],
  "education": [
    {
      "degree": "B.Tech in Computer Science",
      "institution": "University Name",
      "year": "2020",
      "gpa": "8.5/10"
    }
  ],
  "projects": [
    {
      "name": "Project Name",
      "description": "One-line description with tech stack",
      "bullets": ["Built X using Y, achieving Z"],
      "url": "github.com/..."
    }
  ],
  "certifications": ["AWS Solutions Architect – Associate (2023)"],
  "ats_keywords_used": ["list of JD keywords naturally embedded"]
}"""


_COVER_LETTER_SYSTEM = """You are an expert career coach who writes compelling, human-sounding cover letters.
Write a cover letter that:
- Opens with a strong hook (NOT "I am applying for...")
- Connects the candidate's specific experience to the role's needs
- Shows genuine interest in the company
- Is 3 paragraphs, 250-300 words
- Sounds human, NOT robotic or generic
- Ends with a confident call to action

Return ONLY the cover letter text (no JSON, no subject line, no address block)."""


# ── JD Parser ─────────────────────────────────────────────────────────────────
def parse_jd(jd_text: str, client: anthropic.Anthropic) -> dict:
    """Extract structured info from a job description."""
    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            system=_JD_PARSER_SYSTEM,
            messages=[{"role": "user", "content": f"Job Description:\n{jd_text[:4000]}"}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as exc:
        logger.error("JD parsing failed: %s", exc)
        return {
            "required_skills": [],
            "preferred_skills": [],
            "responsibilities": [],
            "experience_years": "",
            "key_keywords": [],
            "seniority": "",
            "role_summary": jd_text[:200],
        }


# ── Resume Rewriter ───────────────────────────────────────────────────────────
def rewrite_resume(
    base_resume: str,
    jd_text: str,
    jd_analysis: dict,
    job_title: str,
    company_name: str,
    client: anthropic.Anthropic,
) -> dict:
    """
    Rewrites the resume dict tailored to the specific JD.
    Returns a structured dict ready for rendering.
    """
    prompt = f"""## Target Job
Title: {job_title}
Company: {company_name}

## Job Description Analysis
{json.dumps(jd_analysis, indent=2)}

## Full Job Description
{jd_text[:3000]}

## Candidate's Base Resume
{base_resume[:4000]}

Rewrite the resume fully tailored for this specific role. Return JSON only."""

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=3000,
            system=_RESUME_REWRITER_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as exc:
        logger.error("Resume rewrite failed: %s", exc)
        # Return a minimal fallback structure
        return _fallback_resume_structure(base_resume, job_title, company_name)


def _fallback_resume_structure(
    resume_text: str, job_title: str, company: str
) -> dict:
    """Minimal structure when AI call fails."""
    lines = [l.strip() for l in resume_text.split("\n") if l.strip()]
    return {
        "name": lines[0] if lines else "Candidate",
        "email": "",
        "phone": "",
        "linkedin": "",
        "github": "",
        "location": "",
        "summary": f"Experienced professional applying for {job_title} at {company}.",
        "skills": {"primary": [], "secondary": []},
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
        "ats_keywords_used": [],
        "_raw_text": resume_text,
    }


# ── Cover Letter Generator ────────────────────────────────────────────────────
def generate_cover_letter(
    resume_dict: dict,
    jd_text: str,
    job_title: str,
    company_name: str,
    jd_analysis: dict,
    client: anthropic.Anthropic,
) -> str:
    """Generate a tailored cover letter as plain text."""
    prompt = f"""
Candidate Name: {resume_dict.get("name", "the candidate")}
Applying For: {job_title} at {company_name}

Key role responsibilities:
{chr(10).join("- " + r for r in jd_analysis.get("responsibilities", [])[:5])}

Candidate's most relevant experience:
{_summarise_experience(resume_dict)}

Candidate's key skills: {", ".join(resume_dict.get("skills", {}).get("primary", [])[:8])}

Write a compelling cover letter.
"""
    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=600,
            system=_COVER_LETTER_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        logger.error("Cover letter generation failed: %s", exc)
        return (
            f"Dear Hiring Manager,\n\n"
            f"I am excited to apply for the {job_title} position at {company_name}. "
            f"My background aligns closely with your requirements.\n\n"
            f"Sincerely,\n{resume_dict.get('name', 'Applicant')}"
        )


def _summarise_experience(resume_dict: dict) -> str:
    exp = resume_dict.get("experience", [])
    if not exp:
        return "Various roles"
    lines = []
    for e in exp[:2]:
        bullets = e.get("bullets", [])
        first = bullets[0] if bullets else ""
        lines.append(
            f"- {e.get('title')} at {e.get('company')} "
            f"({e.get('start_date')}–{e.get('end_date')}): {first}"
        )
    return "\n".join(lines)


# ── ATS Score (post-generation) ───────────────────────────────────────────────
def compute_ats_score(resume_dict: dict, jd_analysis: dict) -> float:
    """
    Simple post-generation ATS score:
    checks how many JD keywords are present in the final resume text.
    """
    resume_text = json.dumps(resume_dict).lower()
    keywords = [k.lower() for k in jd_analysis.get("key_keywords", [])]
    req_skills = [s.lower() for s in jd_analysis.get("required_skills", [])]
    all_targets = list(set(keywords + req_skills))
    if not all_targets:
        return 75.0
    hits = sum(1 for kw in all_targets if kw in resume_text)
    return round(hits / len(all_targets) * 100, 1)


# ── Main orchestration ────────────────────────────────────────────────────────
def generate_tailored_resume(
    base_resume_text: str,
    job: dict,  # matched job dict from matcher.py
    include_cover_letter: bool = True,
) -> dict:
    """
    Full pipeline for one job:
      parse JD → rewrite resume → generate cover letter → score

    Returns:
    {
      "resume": <structured resume dict>,
      "cover_letter": <str>,
      "ats_score": <float>,
      "jd_analysis": <dict>,
      "keyword_gaps": <list>
    }
    """
    if not settings.anthropic_api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Cannot generate tailored resume."
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    jd_text = job.get("description", "")
    job_title = job.get("title", "")
    company_name = job.get("company", "")

    # Step 1: Parse JD
    logger.info("Parsing JD for: %s @ %s", job_title, company_name)
    jd_analysis = parse_jd(jd_text, client)

    # Step 2: Rewrite resume
    logger.info("Rewriting resume for: %s @ %s", job_title, company_name)
    resume_dict = rewrite_resume(
        base_resume=base_resume_text,
        jd_text=jd_text,
        jd_analysis=jd_analysis,
        job_title=job_title,
        company_name=company_name,
        client=client,
    )

    # Step 3: Cover letter
    cover_letter = ""
    if include_cover_letter:
        logger.info("Generating cover letter for: %s @ %s", job_title, company_name)
        cover_letter = generate_cover_letter(
            resume_dict=resume_dict,
            jd_text=jd_text,
            job_title=job_title,
            company_name=company_name,
            jd_analysis=jd_analysis,
            client=client,
        )

    # Step 4: ATS score
    ats_score = compute_ats_score(resume_dict, jd_analysis)

    # Step 5: Keyword gaps (JD required skills not in resume)
    used_kw = set(k.lower() for k in resume_dict.get("ats_keywords_used", []))
    req_skills = [s for s in jd_analysis.get("required_skills", [])
                  if s.lower() not in used_kw]

    return {
        "resume": resume_dict,
        "cover_letter": cover_letter,
        "ats_score": ats_score,
        "jd_analysis": jd_analysis,
        "keyword_gaps": req_skills,
    }
