"""
backend/database.py
SQLAlchemy async models + session factory.
Works with SQLite (dev) and PostgreSQL (prod) — just change DATABASE_URL.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer,
    String, Text, ForeignKey, func,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from backend.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# ── Base ──────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────────────────────────
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200))
    email = Column(String(200), unique=True, index=True)
    base_resume_text = Column(Text)          # raw extracted text
    base_resume_path = Column(String(500))   # path to uploaded file
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    jobs = relationship("JobListing", back_populates="user")
    generated_resumes = relationship("GeneratedResume", back_populates="user")


class JobListing(Base):
    __tablename__ = "job_listings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=True)

    # ── Core fields ───────────────────────────────────────────────────────────
    title = Column(String(300))
    company = Column(String(300))
    location = Column(String(300))
    source = Column(String(50))       # linkedin | indeed | naukri | other
    job_url = Column(String(1000))
    description = Column(Text)
    job_type = Column(String(100))    # full-time, contract, etc.
    salary_range = Column(String(200))
    posted_date = Column(String(100))

    # ── Matching ──────────────────────────────────────────────────────────────
    match_score = Column(Float, default=0.0)
    skills_matched = Column(Text)     # JSON list of matched skills
    skills_missing = Column(Text)     # JSON list of missing skills
    is_relevant = Column(Boolean, default=False)

    # ── Timestamps ───────────────────────────────────────────────────────────
    fetched_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserProfile", back_populates="jobs")
    generated_resumes = relationship("GeneratedResume", back_populates="job")


class GeneratedResume(Base):
    __tablename__ = "generated_resumes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("user_profiles.id"))
    job_id = Column(String, ForeignKey("job_listings.id"))

    resume_text = Column(Text)       # full tailored resume (markdown)
    cover_letter = Column(Text)
    ats_score = Column(Float)
    keyword_gaps = Column(Text)      # JSON list

    pdf_path = Column(String(500))
    docx_path = Column(String(500))
    cover_letter_path = Column(String(500))

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserProfile", back_populates="generated_resumes")
    job = relationship("JobListing", back_populates="generated_resumes")


# ── Helpers ───────────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
