"""Rule-based email drafts stay grounded in supplied research."""
from database.db import get_db, init_db
from database.models import Business, EmailDraft, LeadResearch
from modules.email_generator import generate_email, save_email_draft


def test_rule_based_email_uses_real_context_and_can_be_saved():
    init_db()
    with get_db() as session:
        business = Business(
            name="Harbor Creative",
            normalized_domain="harbor-creative.example",
            website_url="https://harbor-creative.example",
            industry="Digital Marketing Agencies",
            country="India",
            city="Bengaluru",
            business_type="B2B service providers",
            description="Public company description from search.",
            discovery_source="Unit Test",
        )
        session.add(business)
        session.flush()
        business_id = business.id
        session.add(LeadResearch(
            business_id=business_id,
            about_summary="Harbor Creative builds campaigns for business-to-business software companies.",
            services_offered="Account-based marketing and website conversion programs.",
            crawl_status="Completed",
        ))

    for tone in ("Professional", "Friendly", "Direct", "Consultative"):
        draft = generate_email(
            business_id=business_id,
            sender_company="Northline",
            sender_offering="pipeline research workflow",
            value_proposition="prepare a first outreach email with public company context",
            purpose="an introductory call",
            tone=tone,
            use_ollama=False,
        )
        assert "Harbor Creative" in draft["subject"] or "Harbor Creative" in draft["full_body"]
        assert "Northline" in draft["full_body"]
        lowered = draft["full_body"].lower()
        assert "as we discussed" not in lowered
        assert "great meeting you" not in lowered
        assert "we spoke last" not in lowered
        assert draft["call_to_action"]
        assert draft["personalized_opening"]

    draft_id = save_email_draft(
        business_id=business_id,
        email_data=draft,
        sender_company="Northline",
        sender_offering="pipeline research workflow",
        notes="Prepared for review.",
    )
    with get_db() as session:
        stored = session.query(EmailDraft).filter_by(id=draft_id).one()
        assert stored.full_body == draft["full_body"]
        assert stored.notes == "Prepared for review."
        assert stored.outreach_status == "Draft Created"
