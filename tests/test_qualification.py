"""Lead scoring categories and manual overrides."""
from database.db import get_db, init_db
from database.models import Business, LeadResearch
from modules.qualification import calculate_lead_score, override_lead_qualification


def _create_business(**kwargs):
    payload = {
        "name": "Score Target",
        "normalized_domain": kwargs.pop("normalized_domain"),
        "website_url": "https://score-target.example",
        "industry": "Digital Marketing Agencies",
        "country": "India",
        "city": "Bengaluru",
        "business_type": "B2B service providers",
        "description": "Digital marketing services for other businesses.",
        "discovery_source": "Unit Test",
    }
    payload.update(kwargs)
    with get_db() as session:
        business = Business(**payload)
        session.add(business)
        session.flush()
        return business.id


def test_score_bands_and_manual_override():
    init_db()
    rich_id = _create_business(normalized_domain="rich-score.example", name="Rich Score")
    with get_db() as session:
        session.add(LeadResearch(
            business_id=rich_id,
            about_summary="A digital marketing agency working with business clients in Bengaluru.",
            services_offered="SEO, paid media, and content programs for B2B companies.",
            public_email="team@rich-score.example",
            email_status="Found",
            email_source_url="https://rich-score.example/contact",
            public_phone="+91 80 4000 1000",
            phone_status="Needs verification",
            linkedin_url="https://www.linkedin.com/company/rich-score",
            crawl_status="Completed",
        ))

    rich = calculate_lead_score(rich_id)
    assert rich["lead_score"] >= 80
    assert rich["qualification_status"] == "High Priority"
    assert "industry_relevance" in rich["score_breakdown"]
    assert rich["recommended_action"]

    thin_id = _create_business(
        normalized_domain="thin-score.example",
        name="Thin Score",
        industry=None,
        country=None,
        city=None,
        business_type=None,
        description=None,
        website_url="",
    )
    thin = calculate_lead_score(
        thin_id,
        target_industry="Logistics",
        target_business_type="Manufacturer",
        target_country="Germany",
        target_city="Berlin",
    )
    assert thin["lead_score"] < 60
    assert thin["qualification_status"] == "Low Priority"
    assert thin["missing_info"]

    override_lead_qualification(thin_id, 92, "High Priority", "Known account from a referral.")
    preserved = calculate_lead_score(thin_id)
    assert preserved["lead_score"] == 92
    assert preserved["manual_override"] is True
    assert "referral" in preserved["override_reason"]
