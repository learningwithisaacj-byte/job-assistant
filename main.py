"""
backend/main.py
FastAPI application – REST API for the Job Assistant system.

Endpoints:
  POST /api/upload-resume         → parse and store base resume
  POST /api/search-jobs           → scrape + match jobs
  POST /api/generate-resume/{id}  → generate tailored resume for a job
  GET  /api/jobs                  → list stored jobs
  GET  /api/download/{type}/{id}  → download PDF / DOCX
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import (
    Depends, FastAPI, File, Form, HTTPException,
    UploadFile, BackgroundTasks,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import get_settings
from backend.database import (
    AsyncSessionLocal, GeneratedResume, JobListing,
    UserProfile, get_db, init_db,
)
from backend.matcher import match_jobs
from backend.pdf_generator import (
    generate_cover_letter_docx, generate_docx, generate_pdf,
)
from backend.resume_generator import generate_tailored_resume
from backend.scraper import fetch_jobs
from utils.resume_parser import parse_resume_from_bytes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
settings.ensure_output_dir()

app = FastAPI(
    title="Job Assistant API",
    description="AI-powered job search + ATS resume generator",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await init_db()
    logger.info("Database initialised.")


# ── Schemas ───────────────────────────────────────────────────────────────────
class JobSearchRequest(BaseModel):
    keywords: str
    location: str
    experience_level: str = ""           # entry | mid | senior
    sources: List[str] = ["linkedin", "indeed", "naukri"]
    results_per_source: int = 15
    user_id: Optional[str] = None
    use_ai_matching: bool = True


class GenerateResumeRequest(BaseModel):
    user_id: str
    job_id: str
    include_cover_letter: bool = True


# ── Resume upload ─────────────────────────────────────────────────────────────
@app.post("/api/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    name: str = Form(default="User"),
    email: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    """Upload base resume (PDF/DOCX) and extract text."""
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file uploaded.")

    try:
        resume_text = parse_resume_from_bytes(content, file.filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    if not resume_text.strip():
        raise HTTPException(422, "Could not extract text from resume.")

    # Save file
    file_path = settings.output_dir / "uploads" / f"{uuid.uuid4()}_{file.filename}"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)

    # Upsert user
    user = UserProfile(
        id=str(uuid.uuid4()),
        name=name,
        email=email or f"user_{uuid.uuid4().hex[:8]}@temp.com",
        base_resume_text=resume_text,
        base_resume_path=str(file_path),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {
        "user_id": user.id,
        "name": user.name,
        "resume_preview": resume_text[:500] + "...",
        "char_count": len(resume_text),
        "message": "Resume uploaded and parsed successfully.",
    }


# ── Job Search ────────────────────────────────────────────────────────────────
@app.post("/api/search-jobs")
async def search_jobs(
    req: JobSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Scrape jobs from multiple sources, score them against user resume."""

    # Fetch base resume text
    resume_text = ""
    if req.user_id:
        user = await db.get(UserProfile, req.user_id)
        if user:
            resume_text = user.base_resume_text or ""

    # Scrape
    raw_jobs = fetch_jobs(
        keywords=req.keywords,
        location=req.location,
        experience_level=req.experience_level,
        sources=req.sources,
        results_per_source=req.results_per_source,
    )

    if not raw_jobs:
        return {"jobs": [], "total": 0, "message": "No jobs found. Try different keywords."}

    # Match
    if resume_text:
        matched = match_jobs(
            resume_text=resume_text,
            jobs=raw_jobs,
            threshold=settings.match_threshold,
            use_ai=req.use_ai_matching,
        )
    else:
        # No resume: return all jobs with neutral score
        matched = [
            {**j.to_dict(), "match_score": 75.0, "matched_skills": [], "missing_skills": []}
            for j in raw_jobs
        ]

    # Persist to DB
    saved_ids = []
    for m in matched:
        job_db = JobListing(
            id=str(uuid.uuid4()),
            user_id=req.user_id,
            title=m["title"],
            company=m["company"],
            location=m["location"],
            source=m["source"],
            job_url=m["job_url"],
            description=m["description"],
            job_type=m.get("job_type", ""),
            salary_range=m.get("salary_range", ""),
            posted_date=m.get("posted_date", ""),
            match_score=m.get("match_score", 0),
            skills_matched=json.dumps(m.get("matched_skills", [])),
            skills_missing=json.dumps(m.get("missing_skills", [])),
            is_relevant=True,
        )
        db.add(job_db)
        m["job_id"] = job_db.id
        saved_ids.append(job_db.id)

    await db.commit()

    return {
        "jobs": matched,
        "total": len(matched),
        "scraped": len(raw_jobs),
        "threshold_used": settings.match_threshold,
    }


# ── Generate tailored resume ──────────────────────────────────────────────────
@app.post("/api/generate-resume")
async def generate_resume_endpoint(
    req: GenerateResumeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate ATS-tailored resume + cover letter for a specific job."""

    user = await db.get(UserProfile, req.user_id)
    if not user:
        raise HTTPException(404, "User not found. Please upload resume first.")

    job = await db.get(JobListing, req.job_id)
    if not job:
        raise HTTPException(404, "Job not found.")

    job_dict = {
        "title": job.title,
        "company": job.company,
        "description": job.description,
        "location": job.location,
        "source": job.source,
        "job_url": job.job_url,
    }

    # Generate
    try:
        result = generate_tailored_resume(
            base_resume_text=user.base_resume_text,
            job=job_dict,
            include_cover_letter=req.include_cover_letter,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception as exc:
        logger.error("Resume generation failed: %s", exc, exc_info=True)
        raise HTTPException(500, f"Generation failed: {exc}")

    # Save files
    safe_name = (
        f"{job.company}_{job.title}".replace(" ", "_")
                                    .replace("/", "-")[:50]
    )
    gen_id = str(uuid.uuid4())
    pdf_path = settings.output_dir / "resumes" / f"{gen_id}_{safe_name}.pdf"
    docx_path = settings.output_dir / "resumes" / f"{gen_id}_{safe_name}.docx"
    cl_path = settings.output_dir / "cover_letters" / f"{gen_id}_{safe_name}_CL.docx"

    generate_pdf(result["resume"], pdf_path)
    generate_docx(result["resume"], docx_path)

    if result.get("cover_letter"):
        generate_cover_letter_docx(
            result["cover_letter"],
            candidate_name=result["resume"].get("name", ""),
            job_title=job.title,
            company=job.company,
            output_path=cl_path,
        )

    # Persist generated resume
    gen_resume = GeneratedResume(
        id=gen_id,
        user_id=req.user_id,
        job_id=req.job_id,
        resume_text=json.dumps(result["resume"]),
        cover_letter=result.get("cover_letter", ""),
        ats_score=result.get("ats_score", 0),
        keyword_gaps=json.dumps(result.get("keyword_gaps", [])),
        pdf_path=str(pdf_path),
        docx_path=str(docx_path),
        cover_letter_path=str(cl_path) if result.get("cover_letter") else "",
    )
    db.add(gen_resume)
    await db.commit()

    return {
        "generated_id": gen_id,
        "ats_score": result["ats_score"],
        "keyword_gaps": result["keyword_gaps"],
        "jd_analysis": result["jd_analysis"],
        "resume_preview": result["resume"],
        "cover_letter": result.get("cover_letter", ""),
        "downloads": {
            "pdf": f"/api/download/pdf/{gen_id}",
            "docx": f"/api/download/docx/{gen_id}",
            "cover_letter": f"/api/download/cover-letter/{gen_id}" if result.get("cover_letter") else None,
        },
        "message": "Resume generated successfully!",
    }


# ── Downloads ─────────────────────────────────────────────────────────────────
async def _get_gen_resume(gen_id: str, db: AsyncSession) -> GeneratedResume:
    gen = await db.get(GeneratedResume, gen_id)
    if not gen:
        raise HTTPException(404, "Generated resume not found.")
    return gen


@app.get("/api/download/pdf/{gen_id}")
async def download_pdf(gen_id: str, db: AsyncSession = Depends(get_db)):
    gen = await _get_gen_resume(gen_id, db)
    path = Path(gen.pdf_path)
    if not path.exists():
        raise HTTPException(404, "PDF file not found.")
    return FileResponse(str(path), media_type="application/pdf",
                        filename=path.name)


@app.get("/api/download/docx/{gen_id}")
async def download_docx(gen_id: str, db: AsyncSession = Depends(get_db)):
    gen = await _get_gen_resume(gen_id, db)
    path = Path(gen.docx_path)
    if not path.exists():
        raise HTTPException(404, "DOCX file not found.")
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )


@app.get("/api/download/cover-letter/{gen_id}")
async def download_cover_letter(gen_id: str, db: AsyncSession = Depends(get_db)):
    gen = await _get_gen_resume(gen_id, db)
    if not gen.cover_letter_path:
        raise HTTPException(404, "No cover letter for this resume.")
    path = Path(gen.cover_letter_path)
    if not path.exists():
        raise HTTPException(404, "Cover letter file not found.")
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )


# ── Misc ──────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/jobs")
async def list_jobs(
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(JobListing).where(JobListing.is_relevant == True)
    if user_id:
        stmt = stmt.where(JobListing.user_id == user_id)
    stmt = stmt.order_by(JobListing.match_score.desc()).limit(100)
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    return {"jobs": [
        {
            "job_id": j.id, "title": j.title, "company": j.company,
            "location": j.location, "source": j.source, "job_url": j.job_url,
            "match_score": j.match_score, "salary_range": j.salary_range,
            "posted_date": j.posted_date,
        }
        for j in jobs
    ]}
