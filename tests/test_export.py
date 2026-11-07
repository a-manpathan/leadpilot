"""CSV export presets and column names."""
from database.db import get_db, init_db
from database.models import Business, EmailDraft, LeadQualification, LeadResearch
from modules.exporter import export_leads_to_csv
from modules.lead_manager import get_all_leads_enriched


def test_csv_exports_filter_priority_email_and_drafts():
    init_db()
    with get_db() as session:
        high = Business(
            name="High Peak",
            normalized_domain="high-peak.example",
            website_url="https://high-peak.example",
            industry="Software",
            country="India",
            city="Pune",
            discovery_source="Unit Test",
        )
        low = Business(
            name="Low Ridge",
            normalized_domain="low-ridge.example",
            website_url="https://low-ridge.example",
            industry="Software",
            country="India",
            discovery_source="Unit Test",
        )
        session.add_all([high, low])
        session.flush()
        session.add(LeadResearch(
            business_id=high.id,
            public_email="sales@high-peak.example",
            email_status="Needs verification",
            email_source_url="https://high-peak.example/contact",
            crawl_status="Completed",
        ))
        session.add(LeadQualification(
            business_id=high.id,
            lead_score=88,
            qualification_status="High Priority",
            recommended_action="Review the draft.",
        ))
        session.add(LeadQualification(
            business_id=low.id,
            lead_score=40,
            qualification_status="Low Priority",
            recommended_action="Collect more information.",
        ))
        session.add(EmailDraft(
            business_id=high.id,
            subject="Hello High Peak",
            full_body="Draft body for High Peak.",
            outreach_status="Draft Created",
        ))

    leads = get_all_leads_enriched(min_score=80)
    assert [item["name"] for item in leads] == ["High Peak"]

    all_bytes, all_count, all_name = export_leads_to_csv("All Discovered Leads")
    high_bytes, high_count, _ = export_leads_to_csv("High-Priority Leads Only (Score 80-100)")
    email_bytes, email_count, _ = export_leads_to_csv("Leads with Available Email Addresses")
    draft_bytes, draft_count, _ = export_leads_to_csv("Leads with Generated Email Drafts")

    assert all_count == 2
    assert high_count == 1
    assert email_count == 1
    assert draft_count == 1
    assert all_name.endswith(".csv")

    text = all_bytes.decode("utf-8-sig")
    assert text.startswith("Company Name,Website URL")
    assert "Public Email" in text
    assert "Lead Score" in text
    assert "High Peak" in text
    assert "sales@high-peak.example" in email_bytes.decode("utf-8-sig")
    assert "Low Ridge" not in high_bytes.decode("utf-8-sig")
    assert "Draft body for High Peak." in draft_bytes.decode("utf-8-sig")
