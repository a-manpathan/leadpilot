"""
Central configuration module for LeadPilot.
Loads configuration from environment variables or .env file with safe fallbacks.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

def _read_secret(key: str) -> str:
    """Reads a value from the environment, then Streamlit secrets if present."""
    raw = os.getenv(key, "").strip()
    if raw:
        return raw
    try:
        import streamlit as st

        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        return ""
    return ""


# Database URL configuration
def get_database_url() -> str:
    raw_url = _read_secret("DATABASE_URL")
    if not raw_url:
        data_dir = PROJECT_ROOT / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / "leadpilot.db"
        # Convert to standard SQLite URI with forward slashes
        return f"sqlite:///{db_path.as_posix()}"
    
    # SQLAlchemy 2.x compatibility: replace postgres:// with postgresql://
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql://" + raw_url[len("postgres://"):]
    return raw_url

DATABASE_URL = get_database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

# Application Configuration
APP_ENV = os.getenv("APP_ENV", "development")
APP_PORT = int(os.getenv("APP_PORT", "8501"))

# Scraper & Crawler Configuration
MAX_CRAWL_PAGES_PER_SITE = int(os.getenv("MAX_CRAWL_PAGES_PER_SITE", "3"))
HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "8"))
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "1.0"))
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 LeadPilotResearchBot/1.0"
)

# Optional Local AI Model (Ollama)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# Lead Qualification Scoring Criteria & Weights
SCORING_WEIGHTS = {
    "industry_relevance": 30,
    "business_type_match": 25,
    "website_relevance": 20,
    "contact_info": 15,
    "geographic_match": 10,
}

QUALIFICATION_THRESHOLDS = {
    "high_priority": 80,
    "medium_priority": 60,
}

# Outreach statuses
OUTREACH_STATUSES = [
    "Not Started",
    "Draft Created",
    "Reviewed",
    "Ready to Send",
    "Contacted",
]

# Contact verification statuses
CONTACT_STATUS_FOUND = "Found"
CONTACT_STATUS_NEEDS_VERIFICATION = "Needs verification"
CONTACT_STATUS_NOT_FOUND = "Not found"
