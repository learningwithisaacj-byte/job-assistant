"""
backend/scraper.py
Job scraper supporting LinkedIn, Indeed, and Naukri.

Strategy:
  - LinkedIn + Indeed  → python-jobspy  (headless, no auth required)
  - Naukri             → requests + BeautifulSoup (fallback: jobspy)
  - All results are normalised into a common JobResult dataclass.
"""
from __future__ import annotations

import json
import re
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Data contract ─────────────────────────────────────────────────────────────
@dataclass
class JobResult:
    title: str
    company: str
    location: str
    source: str          # linkedin | indeed | naukri | other
    job_url: str
    description: str
    job_type: str = ""
    salary_range: str = ""
    posted_date: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "source": self.source,
            "job_url": self.job_url,
            "description": self.description,
            "job_type": self.job_type,
            "salary_range": self.salary_range,
            "posted_date": self.posted_date,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────
def _clean(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _get_proxies() -> dict:
    if settings.proxy_url:
        return {"http": settings.proxy_url, "https": settings.proxy_url}
    return {}


# ── LinkedIn + Indeed via python-jobspy ───────────────────────────────────────
def scrape_via_jobspy(
    keywords: str,
    location: str,
    sources: List[str],  # ["linkedin", "indeed"]
    results_wanted: int = 15,
    experience_level: str = "",
) -> List[JobResult]:
    """
    Uses python-jobspy which handles anti-bot measures gracefully.
    Docs: https://github.com/Bunsly/JobSpy
    """
    try:
        from jobspy import scrape_jobs  # lazy import – optional dep
    except ImportError:
        logger.warning("python-jobspy not installed. Skipping LinkedIn/Indeed.")
        return []

    results: List[JobResult] = []

    # Map our experience labels to jobspy's
    exp_map = {
        "entry": "entry level",
        "mid": "mid level",
        "senior": "senior level",
        "": None,
    }
    exp = exp_map.get(experience_level.lower(), None)

    try:
        df = scrape_jobs(
            site_name=sources,
            search_term=keywords,
            location=location,
            results_wanted=results_wanted,
            hours_old=72 * 24,          # last 3 days
            country_indeed="India" if "india" in location.lower() else "USA",
            linkedin_fetch_description=True,
            proxies=[settings.proxy_url] if settings.proxy_url else None,
        )

        if df is None or df.empty:
            return []

        for _, row in df.iterrows():
            desc = _clean(row.get("description", ""))
            if not desc:
                continue

            results.append(JobResult(
                title=_clean(row.get("title", "Unknown")),
                company=_clean(row.get("company", "Unknown")),
                location=_clean(row.get("location", location)),
                source=_clean(row.get("site", "unknown")),
                job_url=_clean(row.get("job_url", "")),
                description=desc,
                job_type=_clean(row.get("job_type", "")),
                salary_range=_clean(str(row.get("min_amount", "")))
                             + (" – " + _clean(str(row.get("max_amount", "")))
                                if row.get("max_amount") else ""),
                posted_date=_clean(str(row.get("date_posted", ""))),
                raw=row.to_dict(),
            ))
    except Exception as exc:
        logger.error("jobspy scrape failed: %s", exc, exc_info=True)

    return results


# ── Naukri scraper (BeautifulSoup) ────────────────────────────────────────────
NAUKRI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

NAUKRI_SEARCH_URL = (
    "https://www.naukri.com/jobapi/v3/search"
    "?noOfResults={n}&urlType=search_by_keyword"
    "&searchType=adv&keyword={kw}&location={loc}"
    "&pageNo=1&seoKey={kw}-jobs&src=jobsearchDesk&latLong="
)


def scrape_naukri(
    keywords: str,
    location: str,
    results_wanted: int = 15,
) -> List[JobResult]:
    """
    Calls Naukri's internal JSON API (no Selenium needed for basic listing).
    Falls back gracefully to empty list if the API changes.
    """
    results: List[JobResult] = []
    kw_encoded = keywords.replace(" ", "%20")
    loc_encoded = location.replace(" ", "%20")

    url = NAUKRI_SEARCH_URL.format(
        n=results_wanted, kw=kw_encoded, loc=loc_encoded
    )
    extra_headers = {
        **NAUKRI_HEADERS,
        "Referer": "https://www.naukri.com/",
        "appid": "109",
        "systemid": "Naukri",
    }

    try:
        resp = requests.get(
            url, headers=extra_headers, proxies=_get_proxies(), timeout=20
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Naukri API call failed: %s", exc)
        return []

    jobs_raw = data.get("jobDetails", [])
    for job in jobs_raw:
        try:
            jd = " ".join([
                job.get("jobDescription", ""),
                " ".join(job.get("keySkills", {}).get("label", [])),
                job.get("roleCategory", ""),
            ])
            results.append(JobResult(
                title=_clean(job.get("title", "")),
                company=_clean(job.get("companyName", "")),
                location=_clean(
                    ", ".join(loc.get("label", "")
                              for loc in job.get("placeholders", [])
                              if loc.get("type") == "location")
                ),
                source="naukri",
                job_url="https://www.naukri.com" + job.get("jdURL", ""),
                description=_clean(jd),
                job_type=_clean(job.get("employmentType", "")),
                salary_range=_clean(job.get("salary", "")),
                posted_date=_clean(job.get("footerPlaceholderLabel", "")),
                raw=job,
            ))
        except Exception as exc:
            logger.debug("Naukri parse error for job: %s", exc)
            continue

    return results


# ── Unified scraper ───────────────────────────────────────────────────────────
def fetch_jobs(
    keywords: str,
    location: str,
    experience_level: str = "",
    sources: Optional[List[str]] = None,
    results_per_source: int = 15,
) -> List[JobResult]:
    """
    Main entry point. Aggregates results from all requested sources.

    Args:
        keywords:         e.g. "Python Developer"
        location:         e.g. "Hyderabad, India"
        experience_level: entry | mid | senior | ""
        sources:          list of "linkedin" | "indeed" | "naukri"
        results_per_source: how many listings to try to fetch per site

    Returns:
        Deduplicated list of JobResult objects
    """
    if sources is None:
        sources = ["linkedin", "indeed", "naukri"]

    all_jobs: List[JobResult] = []
    seen_urls: set[str] = set()

    # ── JobSpy sources (LinkedIn + Indeed) ────────────────────────────────────
    jobspy_sources = [s for s in sources if s in ("linkedin", "indeed", "zip_recruiter", "glassdoor")]
    if jobspy_sources:
        logger.info("Scraping via jobspy: %s", jobspy_sources)
        jobs = scrape_via_jobspy(
            keywords=keywords,
            location=location,
            sources=jobspy_sources,
            results_wanted=results_per_source,
            experience_level=experience_level,
        )
        for j in jobs:
            if j.job_url not in seen_urls and j.description:
                seen_urls.add(j.job_url)
                all_jobs.append(j)

    # ── Naukri ────────────────────────────────────────────────────────────────
    if "naukri" in sources:
        logger.info("Scraping Naukri...")
        jobs = scrape_naukri(
            keywords=keywords,
            location=location,
            results_wanted=results_per_source,
        )
        for j in jobs:
            if j.job_url not in seen_urls and j.description:
                seen_urls.add(j.job_url)
                all_jobs.append(j)

    logger.info("Total jobs fetched (before filtering): %d", len(all_jobs))
    return all_jobs
