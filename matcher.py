"""
backend/matcher.py
Scores each job against the user's base resume using:
  1. TF-IDF cosine similarity  (fast, offline)
  2. Claude AI re-ranking      (optional, better quality, costs tokens)
"""
from __future__ import annotations

import json
import logging
import re
from typing import List, Optional, Tuple

import anthropic
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.config import get_settings
from backend.scraper import JobResult

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Skill extraction ──────────────────────────────────────────────────────────
_COMMON_SKILLS = {
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "react", "angular", "vue", "nodejs", "node.js", "django", "flask",
    "fastapi", "spring", "aws", "azure", "gcp", "docker", "kubernetes",
    "terraform", "git", "ci/cd", "sql", "postgresql", "mysql", "mongodb",
    "redis", "kafka", "spark", "hadoop", "airflow", "pandas", "numpy",
    "scikit-learn", "tensorflow", "pytorch", "machine learning", "deep learning",
    "nlp", "computer vision", "data science", "data engineering", "mlops",
    "devops", "linux", "bash", "rest api", "graphql", "microservices",
    "agile", "scrum", "jira", "excel", "power bi", "tableau", "looker",
    "langchain", "llm", "openai", "anthropic", "vector database", "pinecone",
    "html", "css", "sass", "webpack", "next.js", "nuxt", "svelte",
}


def extract_skills(text: str) -> set[str]:
    """Extract known tech skills from free text (case-insensitive)."""
    lower = text.lower()
    found = set()
    for skill in _COMMON_SKILLS:
        # Use word-boundary matching
        if re.search(r"\b" + re.escape(skill) + r"\b", lower):
            found.add(skill)
    return found


def extract_keywords(jd: str, top_n: int = 25) -> List[str]:
    """Return top TF-IDF keywords from a JD."""
    try:
        vec = TfidfVectorizer(
            stop_words="english",
            max_features=top_n,
            ngram_range=(1, 2),
        )
        vec.fit([jd])
        return list(vec.vocabulary_.keys())
    except Exception:
        return []


# ── TF-IDF cosine similarity scorer ──────────────────────────────────────────
def tfidf_score(resume_text: str, jd_text: str) -> float:
    """Returns 0-100 cosine similarity score."""
    try:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vec.fit_transform([resume_text, jd_text])
        score = cosine_similarity(matrix[0], matrix[1])[0][0]
        return round(float(score) * 100, 1)
    except Exception:
        return 0.0


# ── Skills-based overlap score ────────────────────────────────────────────────
def skills_overlap_score(
    resume_text: str, jd_text: str
) -> Tuple[float, List[str], List[str]]:
    """
    Returns:
      - skills match score (0-100)
      - list of matched skills
      - list of missing (gap) skills
    """
    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text)

    if not jd_skills:
        return 50.0, [], []

    matched = resume_skills & jd_skills
    missing = jd_skills - resume_skills

    score = round(len(matched) / len(jd_skills) * 100, 1)
    return score, sorted(matched), sorted(missing)


# ── Claude AI re-ranker ───────────────────────────────────────────────────────
_MATCH_SYSTEM = """You are an expert ATS (Applicant Tracking System) analyst.
Given a candidate's resume and a job description, evaluate the match.

Return ONLY a JSON object with this exact schema:
{
  "overall_score": <integer 0-100>,
  "skills_score": <integer 0-100>,
  "experience_score": <integer 0-100>,
  "reasoning": "<one short sentence>",
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill1", "skill2"]
}

Be strict: 70+ = good match, 50-69 = partial match, <50 = poor match.
Do NOT add any text outside the JSON."""


def ai_match_score(
    resume_text: str,
    jd_text: str,
    client: Optional[anthropic.Anthropic] = None,
) -> dict:
    """
    Use Claude to produce a nuanced match analysis.
    Falls back to TF-IDF if API call fails.
    """
    if not settings.anthropic_api_key:
        logger.warning("No API key – using TF-IDF fallback.")
        return _tfidf_fallback(resume_text, jd_text)

    if client is None:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    prompt = (
        f"## Candidate Resume\n{resume_text[:3000]}\n\n"
        f"## Job Description\n{jd_text[:3000]}\n\n"
        "Evaluate the match and return JSON."
    )

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=512,
            system=_MATCH_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip potential markdown fences
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as exc:
        logger.warning("AI match failed: %s – using TF-IDF fallback", exc)
        return _tfidf_fallback(resume_text, jd_text)


def _tfidf_fallback(resume_text: str, jd_text: str) -> dict:
    tfidf = tfidf_score(resume_text, jd_text)
    skills_sc, matched, missing = skills_overlap_score(resume_text, jd_text)
    overall = round((tfidf * 0.5) + (skills_sc * 0.5), 1)
    return {
        "overall_score": overall,
        "skills_score": skills_sc,
        "experience_score": tfidf,
        "reasoning": "Scored via TF-IDF cosine similarity + skill overlap.",
        "matched_skills": matched,
        "missing_skills": missing,
    }


# ── Batch matcher ─────────────────────────────────────────────────────────────
def match_jobs(
    resume_text: str,
    jobs: List[JobResult],
    threshold: Optional[int] = None,
    use_ai: bool = True,
) -> List[dict]:
    """
    Score a list of jobs against the user resume.

    Returns list of dicts sorted by score descending, filtered by threshold.
    Each dict = job.to_dict() + match fields.
    """
    if threshold is None:
        threshold = settings.match_threshold

    client = None
    if use_ai and settings.anthropic_api_key:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    results = []
    for job in jobs:
        if not job.description:
            continue

        if use_ai and client:
            analysis = ai_match_score(resume_text, job.description, client)
        else:
            analysis = _tfidf_fallback(resume_text, job.description)

        overall = analysis.get("overall_score", 0)
        if overall < threshold:
            continue

        entry = job.to_dict()
        entry.update({
            "match_score": overall,
            "skills_score": analysis.get("skills_score", 0),
            "experience_score": analysis.get("experience_score", 0),
            "match_reasoning": analysis.get("reasoning", ""),
            "matched_skills": analysis.get("matched_skills", []),
            "missing_skills": analysis.get("missing_skills", []),
            "keywords": extract_keywords(job.description),
        })
        results.append(entry)

    results.sort(key=lambda x: x["match_score"], reverse=True)
    logger.info(
        "Matched %d / %d jobs above threshold %d%%",
        len(results), len(jobs), threshold
    )
    return results
