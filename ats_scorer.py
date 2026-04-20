"""
utils/ats_scorer.py
Post-generation ATS audit: keyword density, formatting checks,
section presence, and a final grade.
"""
from __future__ import annotations

import json
import re
from typing import List, Tuple


def keyword_density(text: str, keywords: List[str]) -> Tuple[float, List[str], List[str]]:
    """
    Returns:
      - density score 0-100
      - keywords found
      - keywords missing
    """
    if not keywords:
        return 100.0, [], []
    lower = text.lower()
    found = [kw for kw in keywords if kw.lower() in lower]
    missing = [kw for kw in keywords if kw.lower() not in lower]
    score = round(len(found) / len(keywords) * 100, 1)
    return score, found, missing


def check_formatting(resume_dict: dict) -> List[str]:
    """
    Returns a list of formatting warnings (ATS red flags).
    """
    warnings = []

    # Check section presence
    required = ["summary", "skills", "experience", "education"]
    for sec in required:
        if not resume_dict.get(sec):
            warnings.append(f"Missing section: {sec.upper()}")

    # Check bullet points start with action verbs
    action_verbs = {
        "developed", "built", "architected", "designed", "implemented",
        "led", "managed", "created", "optimised", "delivered", "reduced",
        "increased", "launched", "automated", "migrated", "integrated",
        "collaborated", "maintained", "engineered", "spearheaded",
    }
    for exp in resume_dict.get("experience", []):
        for bullet in exp.get("bullets", []):
            first_word = bullet.split()[0].lower().rstrip(".,") if bullet else ""
            if first_word and first_word not in action_verbs:
                warnings.append(
                    f"Bullet may not start with action verb: '{bullet[:50]}...'"
                )
            break  # only check first bullet per role

    # Check summary length
    summary = resume_dict.get("summary", "")
    if summary and len(summary.split()) < 30:
        warnings.append("Summary is very short (<30 words). Consider expanding.")

    # Check contact info
    for field in ["email", "phone"]:
        if not resume_dict.get(field):
            warnings.append(f"Missing contact field: {field}")

    return warnings


def full_ats_report(
    resume_dict: dict,
    jd_keywords: List[str],
    jd_required_skills: List[str],
) -> dict:
    """
    Generates a full ATS audit report.
    """
    resume_text = json.dumps(resume_dict)

    # Keyword check
    kw_score, kw_found, kw_missing = keyword_density(resume_text, jd_keywords)
    skill_score, skill_found, skill_missing = keyword_density(
        resume_text, jd_required_skills
    )

    # Formatting check
    fmt_warnings = check_formatting(resume_dict)

    # Overall score
    overall = round((kw_score * 0.4) + (skill_score * 0.5) - (len(fmt_warnings) * 2), 1)
    overall = max(0.0, min(100.0, overall))

    # Grade
    if overall >= 85:
        grade = "A"
    elif overall >= 70:
        grade = "B"
    elif overall >= 55:
        grade = "C"
    else:
        grade = "D"

    return {
        "overall_score": overall,
        "grade": grade,
        "keyword_score": kw_score,
        "keywords_found": kw_found,
        "keywords_missing": kw_missing,
        "skill_score": skill_score,
        "skills_found": skill_found,
        "skills_missing": skill_missing,
        "formatting_warnings": fmt_warnings,
        "recommendations": _build_recommendations(kw_missing, skill_missing, fmt_warnings),
    }


def _build_recommendations(
    kw_missing: List[str],
    skill_missing: List[str],
    fmt_warnings: List[str],
) -> List[str]:
    recs = []
    if kw_missing[:3]:
        recs.append(f"Add these JD keywords: {', '.join(kw_missing[:3])}")
    if skill_missing[:3]:
        recs.append(f"Highlight these required skills: {', '.join(skill_missing[:3])}")
    recs.extend(fmt_warnings[:3])
    if not recs:
        recs.append("Resume looks well-optimised for this JD!")
    return recs
