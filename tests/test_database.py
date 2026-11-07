"""Database creation, CRUD, duplicate detection, extraction, and persistence."""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from database.db import get_db, init_db, reset_engine
from database.migrations import export_database_to_json, import_database_from_json
from database.models import Business, LeadResearch
from modules.discovery import save_discovered_leads
from modules.extraction import research_business
from utils.search import is_directory_result
from utils.validators import clean_extracted_email, is_safe_url, normalize_domain


HOME_HTML = """
<html>
  <head><meta name="description" content="Acme provides B2B marketing services for agencies."></head>
  <body>
    <a href="/about">About</a>
    <a href="/contact">Contact</a>
    <a href="mailto:hello@example.org">Email</a>
    <a href="tel:+14155550199">Phone</a>
    <a href="https://www.linkedin.com/company/acme-test">LinkedIn</a>
    <section class="services"><p>We offer SEO, paid media, and content programs for business clients.</p></section>
  </body>
</html>
"""


def _response(url):
    response = MagicMock()
    response.status_code = 200
    response.text = HOME_HTML
    response.headers = {"Content-Type": "text/html; charset=utf-8"}
    response.url = url
    return response


def test_database_creates_tables_and_persists_records(tmp_path):
    init_db()
    with get_db() as session:
        session.add(Business(
            name="Acme Growth",
            normalized_domain="acme-growth.example",
            website_url="https://acme-growth.example",
            industry="Marketing",
            country="India",
            city="Bengaluru",
            business_type="B2B service providers",
            description="A sample record created by the test suite.",
            discovery_source="Unit Test",
        ))

    reset_engine()
    init_db()
    with get_db() as session:
        saved = session.query(Business).filter_by(normalized_domain="acme-growth.example").one()
        assert saved.name == "Acme Growth"
        assert saved.city == "Bengaluru"
        saved_id = saved.id

    with pytest.raises(IntegrityError):
        with get_db() as session:
            session.add(Business(
                name="Duplicate Acme",
                normalized_domain="acme-growth.example",
                website_url="https://acme-growth.example/about",
            ))

    saved_count, skipped = save_discovered_leads([
        {
            "name": "Acme Growth",
            "normalized_domain": "acme-growth.example",
            "website_url": "https://acme-growth.example",
            "industry": "Marketing",
            "country": "India",
            "city": "Bengaluru",
            "business_type": "B2B service providers",
            "description": "Already stored.",
            "discovery_source": "Unit Test",
            "discovery_query": "test",
        },
        {
            "name": "Northwind Studio",
            "normalized_domain": "northwind-studio.example",
            "website_url": "https://northwind-studio.example",
            "industry": "Marketing",
            "country": "India",
            "city": "Bengaluru",
            "business_type": "B2B service providers",
            "description": "Second sample company.",
            "discovery_source": "Sample/Demo Data (Search Fallback)",
            "discovery_query": "test",
        },
    ])
    assert saved_count == 1
    assert skipped == 1

    with get_db() as session:
        business = session.query(Business).filter_by(id=saved_id).one()
        business.website_url = "https://example.org"
        business.normalized_domain = "example.org"

    with patch("modules.extraction.requests.get", side_effect=lambda url, **kwargs: _response(url)):
        result = research_business(saved_id)

    assert result["public_email"] == "hello@example.org"
    assert result["email_status"] == "Found"
    assert result["email_source_url"]
    assert result["public_phone"]
    assert result["linkedin_url"] == "https://www.linkedin.com/company/acme-test"
    assert result["crawled_pages_count"] >= 1

    with get_db() as session:
        research = session.query(LeadResearch).filter_by(business_id=saved_id).one()
        assert research.public_email == "hello@example.org"
        assert research.email_source_url

    backup = export_database_to_json(
        os_database_url(),
        str(tmp_path / "backup.json"),
    )
    second_db = tmp_path / "imported.db"
    imported = import_database_from_json(f"sqlite:///{second_db.as_posix()}", backup)
    assert imported is True


def os_database_url():
    import os
    return os.environ["DATABASE_URL"]


def test_directory_pages_are_not_treated_as_companies():
    assert is_directory_result({
        "title": "Top 10 Digital Marketing Agencies in Bangalore",
        "url": "https://example.org/blog/agencies",
        "is_aggregator": False,
    }) is True
    assert is_directory_result({
        "title": "Monaqo",
        "url": "https://monaqo.in/",
        "is_aggregator": False,
    }) is False
    assert is_directory_result({
        "title": "GoodFirms",
        "url": "https://www.goodfirms.co/directory/city/bangalore",
        "is_aggregator": True,
    }) is True


def test_url_helpers_reject_private_and_junk_contacts():
    assert normalize_domain("https://www.Example.com/path") == "example.com"
    assert clean_extracted_email("hello@example.org") == "hello@example.org"
    assert clean_extracted_email("hello@example.com") is None
    assert clean_extracted_email("user@email.com") is None
    allowed, _ = is_safe_url("https://example.com")
    blocked, reason = is_safe_url("http://127.0.0.1/secret")
    assert allowed is True
    assert blocked is False
    assert "localhost" in reason or "private" in reason or "127" in reason or "loopback" in reason or "internal" in reason or "Unsupported" in reason or "private" in reason.lower() or "blocked" in reason.lower()
