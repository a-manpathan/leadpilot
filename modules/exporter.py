"""
Module 6: CSV Export Engine.
Generates clean, UTF-8 encoded exports with predefined lead qualification filters.
"""
import io
import pandas as pd
from typing import List, Dict, Any, Tuple
from modules.lead_manager import get_all_leads_enriched
from utils.helpers import log_activity


EXPORT_PRESETS = [
    "All Discovered Leads",
    "High-Priority Leads Only (Score 80-100)",
    "Leads with Available Email Addresses",
    "Leads with Generated Email Drafts",
]

COLUMN_MAPPING = {
    "name": "Company Name",
    "website_url": "Website URL",
    "normalized_domain": "Domain",
    "industry": "Industry",
    "business_type": "Business Type",
    "country": "Country",
    "city": "City",
    "description": "Company Description",
    "public_email": "Public Email",
    "email_status": "Email Verification Status",
    "email_source_url": "Email Source URL",
    "public_phone": "Public Phone",
    "phone_status": "Phone Verification Status",
    "contact_page_url": "Contact Page URL",
    "linkedin_url": "LinkedIn Company URL",
    "lead_score": "Lead Score",
    "qualification_status": "Qualification Priority",
    "recommended_action": "Recommended Action",
    "outreach_status": "Outreach Status",
    "email_subject": "Draft Email Subject",
    "email_body": "Draft Email Body",
    "notes": "Outreach Notes",
    "follow_up_date": "Follow-Up Date",
    "date_discovered": "Discovered Date",
    "discovery_source": "Research Source",
}


def filter_leads_for_export(leads: List[Dict[str, Any]], preset: str) -> List[Dict[str, Any]]:
    """Applies preset filter criteria to lead list."""
    if preset == "High-Priority Leads Only (Score 80-100)":
        return [l for l in leads if l.get("lead_score", 0) >= 80]
    elif preset == "Leads with Available Email Addresses":
        return [l for l in leads if l.get("public_email")]
    elif preset == "Leads with Generated Email Drafts":
        return [l for l in leads if l.get("email_body")]
    else:  # All leads
        return leads


def export_leads_to_csv(preset: str = "All Discovered Leads") -> Tuple[bytes, int, str]:
    """
    Exports leads according to preset filter.
    Returns (csv_bytes, record_count, filename).
    """
    raw_leads = get_all_leads_enriched(sort_by="Score (High to Low)")
    filtered = filter_leads_for_export(raw_leads, preset)

    if not filtered:
        # Return empty CSV with headers
        df = pd.DataFrame(columns=list(COLUMN_MAPPING.values()))
    else:
        # Select and rename columns
        rows = []
        for l in filtered:
            row = {}
            for raw_col, clean_col in COLUMN_MAPPING.items():
                val = l.get(raw_col)
                if hasattr(val, "strftime"):
                    val = val.strftime("%Y-%m-%d %H:%M:%S")
                row[clean_col] = val if val is not None else ""
            rows.append(row)
        df = pd.DataFrame(rows)

    # Encode as UTF-8 with BOM (utf-8-sig) for compatibility with MS Excel & international characters
    csv_buffer = io.BytesIO()
    df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    csv_bytes = csv_buffer.getvalue()

    filename_slug = preset.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
    filename = f"leadpilot_{filename_slug}.csv"

    log_activity(
        action="CSV Export",
        target_type="export",
        details=f"Exported {len(filtered)} records using preset '{preset}'.",
    )

    return csv_bytes, len(filtered), filename
