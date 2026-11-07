"""Acceptance tests for the LeadPilot local web app.

These checks follow the project testing list: startup, database creation and
CRUD, sample discovery, website extraction, scoring, email drafts, CSV export,
duplicate detection, and persistence after a restart. External search and live
websites are mocked and labeled so the suite does not depend on a paid API.
"""
import ast
import sys
import types
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from config.settings import (
    QUALIFICATION_THRESHOLDS,
    SCORING_WEIGHTS,
    get_database_url,
)
from database.db import get_db, get_engine, init_db, reset_engine
from database.migrations import export_database_to_json, import_database_from_json
from database.models import (
    ActivityLog,
    Business,
    CompanySettings,
    EmailDraft,
    LeadQualification,
    LeadResearch,
)
from modules.discovery import discover_businesses, generate_search_queries, save_discovered_leads
from modules.email_generator import TONES, generate_email, save_email_draft
from modules.exporter import EXPORT_PRESETS, export_leads_to_csv
from modules.extraction import research_business
from modules.lead_manager import (
    delete_lead,
    get_all_leads_enriched,
    get_lead_by_id,
    update_lead_details,
    update_lead_outreach_status,
)
from modules.qualification import calculate_lead_score, override_lead_qualification
from utils.helpers import get_setting, set_setting
from utils.search import BaseSearchProvider, DuckDuckGoSearchProvider, MockSearchProvider
from utils.validators import clean_extracted_phone, is_safe_url

ROOT = Path(__file__).resolve().parents[1]

HOME_HTML = """
<html>
  <head><meta name="description" content="Northwind provides B2B marketing services."></head>
  <body>
    <a href="/about">About us</a>
    <a href="/contact">Contact</a>
    <a href="/services">Services</a>
    <a href="/team">Team</a>
    <a href="/blog">Blog</a>
    <a href="mailto:hello@northwind.example">Email</a>
    <a href="tel:+14155550198">Call</a>
    <a href="https://www.linkedin.com/company/northwind-example">LinkedIn</a>
    <section class="services"><p>We offer SEO and paid media programs for business clients across India.</p></section>
  </body>
</html>
"""

ABOUT_HTML = """
<html><body><p>Northwind is a digital marketing agency serving business clients in Bengaluru.</p></body></html>
"""

CONTACT_HTML = """
<html><body><p>Reach the team at hello@northwind.example or +1 415 555 0198.</p></body></html>
"""

EMPTY_HTML = """
<html><head><meta name="description" content="A public company page with no contact details."></head>
<body><p>We build software.</p><a href="/about">About</a></body></html>
"""


class _DuplicateProvider(BaseSearchProvider):
    def search(self, query: str, max_results: int = 20):
        item = {
            "title": "Northwind Studio | Official Website",
            "url": "https://www.northwind.example/home",
            "domain": "northwind.example",
            "description": "B2B digital marketing agency in Bengaluru.",
            "source": "DuckDuckGo",
            "is_aggregator": False,
        }
        return [item, dict(item), dict(item)]


class _FailingProvider(BaseSearchProvider):
    def search(self, query: str, max_results: int = 20):
        raise RuntimeError("search provider unavailable")


def _html_response(url):
    response = requests.Response()
    response.status_code = 200
    response.url = url
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    if url.rstrip("/").endswith("/about"):
        body = ABOUT_HTML
    elif url.rstrip("/").endswith("/contact"):
        body = CONTACT_HTML
    elif url.rstrip("/").endswith("/services"):
        body = HOME_HTML
    else:
        body = HOME_HTML
    response._content = body.encode("utf-8")
    return response


def _add_business(**overrides) -> int:
    payload = {
        "name": "Northwind Studio",
        "normalized_domain": "northwind.example",
        "website_url": "https://northwind.example",
        "industry": "Digital Marketing Agencies",
        "country": "India",
        "city": "Bengaluru",
        "business_type": "B2B service providers",
        "description": "B2B digital marketing agency in Bengaluru.",
        "discovery_source": "Unit Test",
        "discovery_query": "Digital Marketing Agencies companies in Bengaluru India",
    }
    payload.update(overrides)
    with get_db() as session:
        business = Business(**payload)
        session.add(business)
        session.flush()
        return business.id


def test_project_files_config_and_deployment_guide_exist():
    required = [
        "app.py",
        "requirements.txt",
        "README.md",
        ".env.example",
        ".gitignore",
        "render.yaml",
        "DEPLOYMENT_GUIDE.md",
        "config/settings.py",
        "database/db.py",
        "database/models.py",
        "database/migrations.py",
        "modules/discovery.py",
        "modules/extraction.py",
        "modules/qualification.py",
        "modules/email_generator.py",
        "modules/lead_manager.py",
        "modules/exporter.py",
        "utils/search.py",
        "utils/validators.py",
        "utils/helpers.py",
        "pages/dashboard.py",
        "pages/discover.py",
        "pages/research.py",
        "pages/qualification.py",
        "pages/email_generator.py",
        "pages/lead_management.py",
        "pages/export.py",
        "pages/settings.py",
        "data/.gitkeep",
        "tests/test_database.py",
        "tests/test_qualification.py",
        "tests/test_email_generator.py",
        "tests/test_export.py",
    ]
    missing = [name for name in required if not (ROOT / name).is_file()]
    assert missing == []

    guide = (ROOT / "DEPLOYMENT_GUIDE.md").read_text(encoding="utf-8")
    for heading in (
        "Part A: Run LeadPilot on your computer",
        "Part B: Put the code on GitHub yourself",
        "Part C: Deploy on Render",
        "Part D: Create the Supabase database",
        "Part E: Update the website later",
        "Part F: Free-plan limits",
        "Vercel",
    ):
        assert heading in guide

    example_env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "sqlite:///./data/leadpilot.db" in example_env
    assert "postgresql://" in example_env
    assert "sk-" not in example_env

    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignore
    assert "*.db" in ignore

    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "streamlit run app.py" in render
    assert "DATABASE_URL" in render

    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    for package in ("streamlit", "pandas", "sqlalchemy", "beautifulsoup4", "requests", "psycopg2-binary"):
        assert package in requirements
    assert "ddgs" in requirements or "duckduckgo-search" in requirements

    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    for title in (
        "Dashboard",
        "Discover Leads",
        "Research & Enrichment",
        "Lead Qualification",
        "Email Generator",
        "Lead Management",
        "Export Data",
        "Settings",
    ):
        assert title in app_source
    assert "does not send email" in app_source

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Vercel" in readme
    assert "python -m database.migrations --export" in readme
    assert not (ROOT / ".github").exists()


def test_interface_exposes_required_controls_and_kpis():
    pages = {
        "pages/dashboard.py": [
            "Total Discovered",
            "High-Priority Leads",
            "Public Emails Found",
            "Drafts Generated",
            "Leads Contacted",
            "Lead Score Distribution",
            "Leads by Industry",
            "Recent discoveries",
            "Outreach Preparation",
        ],
        "pages/discover.py": [
            "Industry or Business Niche",
            "Target Country",
            "Target City",
            "Business Type",
            "Maximum Prospects",
            "Use offline sample data",
            "Save",
        ],
        "pages/research.py": [
            "Run Website Research",
            "About",
        ],
        "pages/qualification.py": [
            "Lead Score",
            "Recommended Next Action",
            "Missing Information",
            "Save Manual Override",
            "does not predict or guarantee internal buying intent",
        ],
        "pages/email_generator.py": [
            "Your Company / Brand Name",
            "Your Product or Service",
            "Value Proposition",
            "Outreach Objective",
            "Desired Email Tone",
            "Generate Email",
            "Regenerate",
            "Copy subject",
            "Copy email body",
            "Save Draft to Lead Record",
            "Automatic sending is intentionally disabled",
        ],
        "pages/lead_management.py": [
            "Search Leads",
            "Industry",
            "Qualification",
            "Minimum lead score",
            "Sort By",
            "Update Company Profile",
            "Internal Sales / Outreach Notes",
            "Follow-Up Calendar Date",
            "Permanently Delete",
        ],
        "pages/export.py": [
            "All Discovered Leads",
            "High-Priority",
            "Email Addresses",
            "Email Drafts",
            "UTF-8",
            "Download CSV",
        ],
        "pages/settings.py": [
            "Your company name",
            "DATABASE_URL",
            "SQLite",
        ],
    }
    for relative, needles in pages.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for needle in needles:
            assert needle in text, f"{relative} is missing {needle}"

    forbidden_modules = {"smtplib", "openai", "boto3"}
    for path in ROOT.rglob("*.py"):
        if "tests" in path.parts or "__pycache__" in path.parts or ".pytest_cache" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".")[0]}
            else:
                continue
            assert names.isdisjoint(forbidden_modules), f"{path.name} imports {names & forbidden_modules}"


def test_database_schema_crud_duplicates_and_restart(tmp_path, monkeypatch):
    init_db()
    tables = set(inspect(get_engine()).get_table_names())
    assert {
        "businesses",
        "lead_research",
        "email_drafts",
        "activity_logs",
        "company_settings",
    } <= tables

    business_columns = {col["name"] for col in inspect(get_engine()).get_columns("businesses")}
    assert {"id", "name", "normalized_domain", "website_url", "created_at", "updated_at"} <= business_columns
    indexes = inspect(get_engine()).get_indexes("businesses")
    unique_constraints = inspect(get_engine()).get_unique_constraints("businesses")
    domain_is_unique = any(
        "normalized_domain" in (item.get("column_names") or [])
        for item in list(indexes) + list(unique_constraints)
    )
    assert domain_is_unique

    import os

    original_url = os.environ["DATABASE_URL"]
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert get_database_url().startswith("sqlite:///")
    monkeypatch.setenv("DATABASE_URL", "postgres://user:secret@db.example:5432/postgres")
    rewritten = get_database_url()
    assert rewritten.startswith("postgresql://")
    monkeypatch.setenv("DATABASE_URL", original_url)

    business_id = _add_business()
    with get_db() as session:
        session.add(LeadResearch(
            business_id=business_id,
            public_email="hello@northwind.example",
            email_status="Needs verification",
            email_source_url="https://northwind.example/contact",
            public_phone="+1 415 555 0198",
            phone_status="Needs verification",
            phone_source_url="https://northwind.example/contact",
            contact_page_url="https://northwind.example/contact",
            linkedin_url="https://www.linkedin.com/company/northwind-example",
            crawl_status="Completed",
        ))
        session.add(LeadQualification(
            business_id=business_id,
            lead_score=72,
            qualification_status="Medium Priority",
            recommended_action="Review the public profile.",
        ))
        session.add(EmailDraft(
            business_id=business_id,
            subject="Hello",
            full_body="Draft body",
            notes="Call the main office.",
            outreach_status="Reviewed",
        ))
        session.add(CompanySettings(key="sender_company", value="Northline"))

    with pytest.raises(IntegrityError):
        _add_business(name="Duplicate domain")

    reset_engine()
    init_db()
    restored = get_lead_by_id(business_id)
    assert restored["name"] == "Northwind Studio"
    assert restored["public_email"] == "hello@northwind.example"
    assert restored["email_source_url"] == "https://northwind.example/contact"
    assert restored["lead_score"] == 72
    assert restored["notes"] == "Call the main office."
    assert get_setting("sender_company") == "Northline"

    with get_db() as session:
        assert session.query(ActivityLog).count() >= 0

    source_url = __import__("os").environ["DATABASE_URL"]
    backup = export_database_to_json(source_url, str(tmp_path / "leadpilot_backup.json"))
    target = tmp_path / "migrated.db"
    assert import_database_from_json(f"sqlite:///{target.as_posix()}", backup) is True


def test_sample_discovery_dedupes_and_labels_fallback_data():
    queries = generate_search_queries(
        "Digital Marketing Agencies",
        "India",
        "Bengaluru",
        "B2B service providers",
    )
    assert any("Digital Marketing Agencies" in query and "Bengaluru" in query and "India" in query for query in queries)
    assert any("B2B service providers" in query for query in queries)
    nationwide = generate_search_queries("Logistics", "Germany", "", "")
    assert all("city" not in query.lower() for query in nationwide)

    leads, stats = discover_businesses(
        industry="Digital Marketing Agencies",
        country="India",
        city="Bengaluru",
        business_type="B2B service providers",
        max_results=30,
        search_provider=_DuplicateProvider(),
    )
    assert stats["duplicates_in_run"] >= 1
    assert len(leads) == 1
    lead = leads[0]
    assert lead["name"] == "Northwind Studio"
    assert lead["website_url"] == "https://www.northwind.example/home"
    assert lead["description"]
    assert lead["discovery_source"] == "DuckDuckGo"
    assert "public_email" not in lead

    saved, skipped = save_discovered_leads(leads)
    assert (saved, skipped) == (1, 0)
    saved_again, skipped_again = save_discovered_leads(leads)
    assert (saved_again, skipped_again) == (0, 1)

    fallback, fallback_stats = discover_businesses(
        industry="Digital Marketing Agencies",
        country="India",
        city="Bengaluru",
        business_type="B2B service providers",
        max_results=5,
        search_provider=_FailingProvider(),
    )
    assert fallback_stats["fallback_used"] is True
    assert fallback
    assert all("Sample/Demo Data" in item["discovery_source"] for item in fallback)
    assert all(item["website_url"].endswith(".example.com") or ".example.com" in item["website_url"] for item in fallback)

    mock_leads, _ = discover_businesses(
        industry="Digital Marketing Agencies",
        country="India",
        city="",
        business_type="",
        max_results=5,
        search_provider=MockSearchProvider(),
    )
    assert all(item["discovery_source"].startswith("Sample/Demo Data") for item in mock_leads)


def test_duckduckgo_provider_is_replaceable_and_waits_between_queries(monkeypatch):
    slept = []
    fake_ddgs = types.ModuleType("ddgs")

    class _DDGS:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def text(self, query, max_results=10):
            return [{
                "title": "Real Co",
                "href": "https://realco.example/about",
                "body": "Public description from search.",
            }]

    fake_ddgs.DDGS = _DDGS
    monkeypatch.setitem(sys.modules, "ddgs", fake_ddgs)
    monkeypatch.setattr("utils.search.time.sleep", lambda seconds: slept.append(seconds))

    provider = DuckDuckGoSearchProvider(request_delay=0.5)
    results = provider.search("digital marketing agencies Bengaluru", max_results=5)
    assert results[0]["source"] == "DuckDuckGo"
    assert results[0]["domain"] == "realco.example"
    assert results[0]["description"] == "Public description from search."
    assert slept == [0.5]
    assert isinstance(provider, BaseSearchProvider)


def test_website_extraction_uses_public_pages_only(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs.get("timeout")))
        if "blocked" in url:
            raise requests.Timeout("timed out")
        response = _html_response(url) if "empty" not in url else _html_response(url)
        if "empty" in url:
            response._content = EMPTY_HTML.encode("utf-8")
        return response

    monkeypatch.setattr("modules.extraction.requests.get", fake_get)
    monkeypatch.setattr("modules.extraction.time.sleep", lambda *_args, **_kwargs: None)

    business_id = _add_business()
    result = research_business(business_id)
    assert len(calls) <= 3
    assert all(timeout is not None and timeout > 0 for _, timeout in calls)
    assert result["public_email"] == "hello@northwind.example"
    assert result["email_status"] in ("Found", "Needs verification")
    assert result["email_source_url"].startswith("https://northwind.example")
    assert result["public_phone"]
    assert result["phone_source_url"]
    assert result["linkedin_url"] == "https://www.linkedin.com/company/northwind-example"
    assert result["contact_page_url"]
    assert result["about_summary"]
    assert result["services_offered"]
    assert result["crawled_pages_count"] <= 3

    with get_db() as session:
        stored = session.query(LeadResearch).filter_by(business_id=business_id).one()
        assert stored.email_source_url == result["email_source_url"]
        assert stored.phone_source_url == result["phone_source_url"]

    empty_id = _add_business(
        name="Empty Site",
        normalized_domain="empty-site.example",
        website_url="https://empty-site.example",
    )
    empty = research_business(empty_id)
    assert empty["public_email"] is None
    assert empty["public_phone"] is None
    assert empty["email_status"] == "Not found"
    assert empty["phone_status"] == "Not found"

    blocked_id = _add_business(
        name="Blocked Site",
        normalized_domain="blocked-site.example",
        website_url="https://blocked-site.example",
    )
    blocked = research_business(blocked_id)
    assert blocked["crawl_status"] == "Blocked"
    assert blocked["public_email"] is None
    assert blocked["public_phone"] is None

    private_id = _add_business(
        name="Private Site",
        normalized_domain="private.example",
        website_url="http://127.0.0.1/admin",
    )
    before = len(calls)
    private = research_business(private_id)
    assert len(calls) == before
    assert private["public_email"] is None
    assert private["crawl_status"] == "Blocked"


def test_security_guards_reject_unsafe_urls_and_junk_contacts():
    for url in ("file:///etc/passwd", "javascript:alert(1)", "http://localhost/admin", "http://169.254.169.254/"):
        allowed, _reason = is_safe_url(url)
        assert allowed is False
    assert clean_extracted_phone("2024") is None
    assert clean_extracted_phone("00000000") is None
    assert clean_extracted_phone("+1 415 555 0198")


def test_scoring_uses_published_weights_bands_and_manual_override():
    assert SCORING_WEIGHTS == {
        "industry_relevance": 30,
        "business_type_match": 25,
        "website_relevance": 20,
        "contact_info": 15,
        "geographic_match": 10,
    }
    assert sum(SCORING_WEIGHTS.values()) == 100
    assert QUALIFICATION_THRESHOLDS["high_priority"] == 80
    assert QUALIFICATION_THRESHOLDS["medium_priority"] == 60

    medium_id = _add_business(
        name="Medium Fit",
        normalized_domain="medium-fit.example",
        description="Digital marketing agencies for other companies.",
    )
    medium = calculate_lead_score(medium_id)
    assert 60 <= medium["lead_score"] <= 79
    assert medium["qualification_status"] == "Medium Priority"
    assert set(medium["score_breakdown"]) == set(SCORING_WEIGHTS)
    for key, item in medium["score_breakdown"].items():
        assert 0 <= item["points"] <= item["max"] == SCORING_WEIGHTS[key]
    assert medium["recommended_action"]
    assert "buying intent" not in medium["recommended_action"].lower()

    low_id = _add_business(
        name="Low Fit",
        normalized_domain="low-fit.example",
        industry=None,
        country=None,
        city=None,
        business_type=None,
        description=None,
        website_url="",
    )
    low = calculate_lead_score(
        low_id,
        target_industry="Logistics",
        target_business_type="Manufacturer",
        target_country="Germany",
        target_city="Berlin",
    )
    assert low["lead_score"] < 60
    assert low["qualification_status"] == "Low Priority"
    assert low["missing_info"]

    rich_id = _add_business(name="Rich Fit", normalized_domain="rich-fit.example")
    with get_db() as session:
        session.add(LeadResearch(
            business_id=rich_id,
            about_summary="A digital marketing agency working with business clients in Bengaluru for many years.",
            services_offered="SEO, paid media, and content programs for B2B companies.",
            public_email="team@rich-fit.example",
            email_status="Needs verification",
            email_source_url="https://rich-fit.example/contact",
            public_phone="+91 80 4000 1000",
            phone_status="Needs verification",
            linkedin_url="https://www.linkedin.com/company/rich-fit",
            crawl_status="Completed",
        ))
    rich = calculate_lead_score(rich_id)
    assert 80 <= rich["lead_score"] <= 100
    assert rich["qualification_status"] == "High Priority"

    override_lead_qualification(low_id, 55, "Low Priority", "Manual review after a call.")
    preserved = calculate_lead_score(low_id)
    assert preserved["lead_score"] == 55
    assert preserved["qualification_status"] == "Low Priority"
    assert preserved["manual_override"] is True


def test_email_drafts_cover_every_tone_and_are_not_sent():
    business_id = _add_business()
    with get_db() as session:
        session.add(LeadResearch(
            business_id=business_id,
            about_summary="Northwind Studio builds campaigns for business-to-business software companies.",
            services_offered="Account-based marketing and website conversion programs.",
            public_email="hello@northwind.example",
            email_status="Needs verification",
            email_source_url="https://northwind.example/contact",
            crawl_status="Completed",
        ))

    forbidden = (
        "as we discussed",
        "great meeting you",
        "we spoke last",
        "our previous call",
        "last time we met",
        "following up on our conversation",
    )
    last_draft = None
    for tone in TONES:
        draft = generate_email(
            business_id=business_id,
            sender_company="Northline",
            sender_offering="pipeline research workflow",
            value_proposition="prepare a first outreach email with public company context",
            purpose="an introductory call",
            tone=tone,
            use_ollama=False,
        )
        for key in ("subject", "personalized_opening", "business_context", "value_proposition", "call_to_action", "full_body"):
            assert draft[key]
        assert "Northwind" in draft["full_body"]
        assert "Northline" in draft["full_body"]
        lowered = draft["full_body"].lower()
        for phrase in forbidden:
            assert phrase not in lowered
        last_draft = draft

    with patch("modules.email_generator.requests.post") as post:
        generate_email(
            business_id=business_id,
            sender_company="Northline",
            sender_offering="pipeline research workflow",
            value_proposition="prepare a first outreach email with public company context",
            purpose="an introductory call",
            tone="Professional",
            use_ollama=False,
        )
        post.assert_not_called()

    draft_id = save_email_draft(
        business_id=business_id,
        email_data=last_draft,
        sender_company="Northline",
        sender_offering="pipeline research workflow",
        notes="Ready for a human to review.",
        follow_up_date=date(2026, 12, 1),
    )
    with get_db() as session:
        stored = session.query(EmailDraft).filter_by(id=draft_id).one()
        assert stored.subject == last_draft["subject"]
        assert stored.full_body == last_draft["full_body"]
        assert stored.follow_up_date is not None
        assert stored.outreach_status == "Draft Created"


def test_lead_management_search_filter_sort_edit_notes_and_delete():
    alpha_id = _add_business(name="Alpha Systems", normalized_domain="alpha.example", industry="Software", city="Pune")
    zeta_id = _add_business(name="Zeta Logistics", normalized_domain="zeta.example", industry="Logistics", city="Berlin", country="Germany")
    with get_db() as session:
        session.add(LeadQualification(business_id=alpha_id, lead_score=90, qualification_status="High Priority"))
        session.add(LeadQualification(business_id=zeta_id, lead_score=40, qualification_status="Low Priority"))
        session.add(LeadResearch(
            business_id=alpha_id,
            public_email="sales@alpha.example",
            email_status="Needs verification",
            email_source_url="https://alpha.example/contact",
        ))

    assert [item["name"] for item in get_all_leads_enriched(search_query="alpha")] == ["Alpha Systems"]
    assert [item["name"] for item in get_all_leads_enriched(industry_filter="Logistics")] == ["Zeta Logistics"]
    assert [item["name"] for item in get_all_leads_enriched(qualification_filter="High Priority")] == ["Alpha Systems"]
    assert [item["name"] for item in get_all_leads_enriched(min_score=80)] == ["Alpha Systems"]
    names = [item["name"] for item in get_all_leads_enriched(sort_by="Company Name (A-Z)")]
    assert names == ["Alpha Systems", "Zeta Logistics"]

    assert update_lead_details(
        alpha_id,
        name="Alpha Systems Updated",
        industry="Software",
        country="India",
        city="Pune",
        business_type="B2B service providers",
        description="Updated description",
        website_url="https://alpha.example",
    )
    assert update_lead_outreach_status(
        alpha_id,
        outreach_status="Contacted",
        notes="Spoke with the front desk.",
        follow_up_date=date(2026, 11, 20),
    )
    updated = get_lead_by_id(alpha_id)
    assert updated["name"] == "Alpha Systems Updated"
    assert updated["description"] == "Updated description"
    assert updated["outreach_status"] == "Contacted"
    assert updated["notes"] == "Spoke with the front desk."
    assert updated["follow_up_date"] is not None
    assert [item["name"] for item in get_all_leads_enriched(outreach_filter="Contacted")] == ["Alpha Systems Updated"]

    reset_engine()
    init_db()
    assert get_lead_by_id(alpha_id)["notes"] == "Spoke with the front desk."

    assert delete_lead(zeta_id) is True
    assert get_lead_by_id(zeta_id) is None
    assert delete_lead(zeta_id) is False


def test_csv_exports_match_the_four_required_presets():
    high_id = _add_business(name="High Peak", normalized_domain="high-peak.example", industry="Software")
    low_id = _add_business(name="Low Ridge", normalized_domain="low-ridge.example", industry="Software")
    with get_db() as session:
        session.add(LeadResearch(
            business_id=high_id,
            public_email="sales@high-peak.example",
            email_status="Needs verification",
            email_source_url="https://high-peak.example/contact",
        ))
        session.add(LeadQualification(business_id=high_id, lead_score=88, qualification_status="High Priority"))
        session.add(LeadQualification(business_id=low_id, lead_score=40, qualification_status="Low Priority"))
        session.add(EmailDraft(
            business_id=high_id,
            subject="Hello High Peak",
            full_body="Draft body for High Peak.",
            outreach_status="Draft Created",
        ))

    assert EXPORT_PRESETS == [
        "All Discovered Leads",
        "High-Priority Leads Only (Score 80-100)",
        "Leads with Available Email Addresses",
        "Leads with Generated Email Drafts",
    ]
    all_bytes, all_count, all_name = export_leads_to_csv(EXPORT_PRESETS[0])
    high_bytes, high_count, _ = export_leads_to_csv(EXPORT_PRESETS[1])
    email_bytes, email_count, _ = export_leads_to_csv(EXPORT_PRESETS[2])
    draft_bytes, draft_count, _ = export_leads_to_csv(EXPORT_PRESETS[3])

    assert (all_count, high_count, email_count, draft_count) == (2, 1, 1, 1)
    assert all_name.endswith(".csv")
    assert all_bytes.startswith(b"\xef\xbb\xbf")
    text = all_bytes.decode("utf-8-sig")
    assert "Company Name" in text
    assert "Public Email" in text
    assert "Lead Score" in text
    assert "Email Source URL" in text
    assert "Low Ridge" not in high_bytes.decode("utf-8-sig")
    assert "sales@high-peak.example" in email_bytes.decode("utf-8-sig")
    assert "Draft body for High Peak." in draft_bytes.decode("utf-8-sig")


def test_streamlit_pages_start_and_show_saved_leads():
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    business_id = _add_business(name="Dashboard Co", normalized_domain="dashboard-co.example")
    with get_db() as session:
        session.add(LeadQualification(
            business_id=business_id,
            lead_score=91,
            qualification_status="High Priority",
            recommended_action="Prepare an email draft.",
        ))
        session.add(LeadResearch(
            business_id=business_id,
            public_email="hello@dashboard-co.example",
            email_status="Needs verification",
            email_source_url="https://dashboard-co.example/contact",
            crawl_status="Completed",
        ))
        session.add(EmailDraft(
            business_id=business_id,
            subject="Hello Dashboard Co",
            full_body="Saved draft body.",
            outreach_status="Contacted",
        ))
    set_setting("sender_company", "Northline")

    dashboard = streamlit_testing.AppTest.from_file(str(ROOT / "pages" / "dashboard.py"))
    dashboard.run(timeout=30)
    assert not dashboard.exception, dashboard.exception
    labels = {metric.label for metric in dashboard.metric}
    assert "Total Discovered" in labels
    assert "High-Priority Leads" in labels
    assert "Public Emails Found" in labels
    assert "Drafts Generated" in labels
    assert "Leads Contacted" in labels
    values = {metric.label: str(metric.value) for metric in dashboard.metric}
    assert values["Total Discovered"] == "1"
    assert values["High-Priority Leads"] == "1"
    assert values["Public Emails Found"] == "1"
    assert values["Drafts Generated"] == "1"
    assert values["Leads Contacted"] == "1"

    discover = streamlit_testing.AppTest.from_file(str(ROOT / "pages" / "discover.py"))
    discover.run(timeout=30)
    assert not discover.exception, discover.exception
    assert any("Industry" in widget.label for widget in discover.text_input)

    export_page = streamlit_testing.AppTest.from_file(str(ROOT / "pages" / "export.py"))
    export_page.run(timeout=30)
    assert not export_page.exception, export_page.exception
    assert any("Prepare CSV" in widget.label for widget in export_page.button)

    app = streamlit_testing.AppTest.from_file(str(ROOT / "app.py"))
    app.run(timeout=30)
    assert not app.exception, app.exception


def test_python_modules_parse():
    for path in ROOT.rglob("*.py"):
        if ".pytest_cache" in path.parts or "__pycache__" in path.parts:
            continue
        ast.parse(path.read_text(encoding="utf-8"))
