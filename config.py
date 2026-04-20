"""
backend/config.py
Central settings – reads from .env via pydantic-settings.
"""
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── AI ────────────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./job_assistant.db"

    # ── App ───────────────────────────────────────────────────────────────────
    secret_key: str = "change-me"
    environment: str = "development"
    output_dir: Path = Path("./outputs")

    # ── Scraping ──────────────────────────────────────────────────────────────
    proxy_url: str = ""
    scraper_results_wanted: int = 20   # jobs per source per search

    # ── Matching ──────────────────────────────────────────────────────────────
    match_threshold: int = 65

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def ensure_output_dir(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()
