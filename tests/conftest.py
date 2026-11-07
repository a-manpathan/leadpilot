"""Point tests at a temporary SQLite file before application modules are imported."""
import os
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent / "_tmp"
TEST_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB = TEST_DIR / "leadpilot_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["REQUEST_DELAY_SECONDS"] = "0"
os.environ["HTTP_TIMEOUT_SECONDS"] = "3"
os.environ["MAX_CRAWL_PAGES_PER_SITE"] = "3"

import pytest


@pytest.fixture(autouse=True)
def clean_database():
    """Each test starts from an empty LeadPilot database."""
    from database.db import get_db, init_db
    from database.models import (
        ActivityLog,
        Business,
        CompanySettings,
        EmailDraft,
        LeadQualification,
        LeadResearch,
    )

    init_db()
    with get_db() as session:
        session.query(EmailDraft).delete()
        session.query(LeadQualification).delete()
        session.query(LeadResearch).delete()
        session.query(ActivityLog).delete()
        session.query(CompanySettings).delete()
        session.query(Business).delete()
    yield
