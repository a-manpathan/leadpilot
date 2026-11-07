"""
Module 4: Personalized Cold Outreach Email Generator.
Generates structured B2B outreach emails across 4 tones using grounded research data.
Zero paid APIs. Includes optional local Ollama LLM support with rule-based fallback.
"""
import json
import logging
from datetime import date, datetime
from typing import Dict, Any, Optional
import requests
from config.settings import OLLAMA_BASE_URL, OLLAMA_MODEL
from database.db import get_db
from database.models import Business, LeadResearch, EmailDraft
from utils.helpers import log_activity

logger = logging.getLogger("leadpilot.email_generator")

TONES = ["Professional", "Friendly", "Direct", "Consultative"]


def check_ollama_status() -> tuple[bool, str]:
    """Checks if a local Ollama instance is available without throwing errors."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=2)
        if resp.status_code == 200:
            models = [m.get("name") for m in resp.json().get("models", [])]
            return True, f"Ollama is running ({len(models)} model(s) available)."
        return False, f"Ollama replied with status {resp.status_code}"
    except Exception:
        return False, "Ollama local server not detected (rule-based generator active)."


def generate_email_rule_based(
    business_name: str,
    industry: str,
    about_summary: str,
    services_offered: str,
    city: str,
    sender_company: str,
    sender_offering: str,
    value_proposition: str,
    purpose: str,
    tone: str = "Professional",
) -> Dict[str, str]:
    """
    Grounded, template & rule-based email generator.
    Never hallucinates previous conversations or fake personal acquaintances.
    """
    biz_clean = business_name.strip()
    loc_clause = f" in {city}" if city else ""
    ind_clause = industry.lower() if industry else "your sector"
    
    # Grounded context snippet
    context_snippet = ""
    if services_offered and len(services_offered) > 20:
        context_snippet = f"Noticed your focus on {services_offered[:120].rstrip('.')}."
    elif about_summary and len(about_summary) > 20:
        context_snippet = f"I came across your work in {ind_clause}{loc_clause}."
    else:
        context_snippet = f"I have been researching growing businesses in the {ind_clause} space{loc_clause}."

    # 1. Professional Tone
    if tone == "Professional":
        subject = f"Exploring a potential collaboration with {biz_clean}"
        opening = f"Dear {biz_clean} Team,"
        context = (
            f"{context_snippet} Your company's established presence in {ind_clause} caught our attention."
        )
        val_prop = (
            f"At {sender_company}, we provide {sender_offering}. "
            f"Specifically, we help our partners {value_proposition.lower().rstrip('.')}."
        )
        cta = (
            f"Given your focus, I would welcome the opportunity to discuss how this could align with "
            f"your current objectives for {purpose.lower() if purpose else 'growth'}. "
            f"Would you be open to a brief 15-minute conversation next week?"
        )
        signoff = f"Best regards,\n[Your Name]\n[Your Title]\n{sender_company}"

    # 2. Friendly Tone
    elif tone == "Friendly":
        subject = f"Quick question regarding {biz_clean}'s {ind_clause} initiatives"
        opening = f"Hi {biz_clean} team,"
        context = (
            f"Hope your week is going great! {context_snippet} Really impressed by what {biz_clean} has built."
        )
        val_prop = (
            f"I'm reaching out from {sender_company}. We've built {sender_offering} designed to {value_proposition.lower().rstrip('.')}."
        )
        cta = (
            f"I'd love to share a few practical ideas tailored to your team regarding {purpose.lower() if purpose else 'collaboration'}. "
            f"Do you have 10 minutes for a quick coffee chat over Zoom this Thursday or Friday?"
        )
        signoff = f"Cheers,\n[Your Name]\n{sender_company}"

    # 3. Direct Tone
    elif tone == "Direct":
        subject = f"{sender_offering} for {biz_clean}"
        opening = f"Hello {biz_clean} Leadership,"
        context = (
            f"{context_snippet} Reaching out with a specific proposal."
        )
        val_prop = (
            f"{sender_company} assists {ind_clause} companies to {value_proposition.lower().rstrip('.')} "
            f"through our {sender_offering}."
        )
        cta = (
            f"If {purpose.lower() if purpose else 'improving efficiency'} is on your roadmap this quarter, "
            f"are you available for a 10-minute introductory call Tuesday at 2 PM?"
        )
        signoff = f"Regards,\n[Your Name]\n{sender_company}"

    # 4. Consultative Tone
    else:  # Consultative
        subject = f"Observations on {ind_clause} growth & {biz_clean}"
        opening = f"Dear {biz_clean} Team,"
        context = (
            f"While researching leaders in the {ind_clause} space{loc_clause}, "
            f"{context_snippet} I noted the strategic positioning of {biz_clean}."
        )
        val_prop = (
            f"Many organizations in your industry face challenges scaling their operations efficiently. "
            f"At {sender_company}, our {sender_offering} is structured to {value_proposition.lower().rstrip('.')}."
        )
        cta = (
            f"I would be glad to share some benchmarks we've observed in your market to assist with your {purpose.lower() if purpose else 'strategic planning'}. "
            f"Would you be open to an exchange of perspectives this coming week?"
        )
        signoff = f"Sincerely,\n[Your Name]\n[Your Title]\n{sender_company}"

    full_body = f"{opening}\n\n{context}\n\n{val_prop}\n\n{cta}\n\n{signoff}"

    return {
        "subject": subject,
        "personalized_opening": opening,
        "business_context": context,
        "value_proposition": val_prop,
        "call_to_action": cta,
        "full_body": full_body,
        "tone": tone,
    }


def generate_email_ollama(
    business_name: str,
    industry: str,
    about_summary: str,
    services_offered: str,
    city: str,
    sender_company: str,
    sender_offering: str,
    value_proposition: str,
    purpose: str,
    tone: str = "Professional",
) -> Optional[Dict[str, str]]:
    """Generates email via local Ollama instance if active."""
    prompt = f"""You are a professional B2B outreach specialist. Generate a customized cold email.
Strict rules:
1. Ground the email in the prospect's real data. Do NOT invent prior relationships or fake meetings.
2. Output JSON with exactly these keys: "subject", "personalized_opening", "business_context", "value_proposition", "call_to_action", "full_body".
3. Desired tone: {tone}

Prospect info:
- Business: {business_name}
- Industry: {industry}
- Location: {city}
- About: {about_summary}
- Services: {services_offered}

Sender info:
- Company: {sender_company}
- Offering: {sender_offering}
- Value Prop: {value_proposition}
- Outreach Purpose: {purpose}
"""
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }
        resp = requests.post(f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate", json=payload, timeout=20)
        if resp.status_code == 200:
            parsed = json.loads(resp.json().get("response", "{}"))
            if "subject" in parsed and "full_body" in parsed:
                parsed["tone"] = tone
                return parsed
    except Exception as e:
        logger.warning(f"Ollama generation failed: {e}. Falling back to rule-based engine.")
    return None


def generate_email(
    business_id: int,
    sender_company: str,
    sender_offering: str,
    value_proposition: str,
    purpose: str,
    tone: str = "Professional",
    use_ollama: bool = False,
) -> Dict[str, str]:
    """Generates personalized email for a business using grounded data."""
    with get_db() as session:
        business = session.query(Business).filter_by(id=business_id).first()
        if not business:
            raise ValueError(f"Business {business_id} not found.")

        research = session.query(LeadResearch).filter_by(business_id=business_id).first()
        about = research.about_summary if research else ""
        services = research.services_offered if research else ""
        city = business.city or ""
        industry = business.industry or ""
        name = business.name

    if use_ollama:
        ollama_res = generate_email_ollama(
            business_name=name,
            industry=industry,
            about_summary=about,
            services_offered=services,
            city=city,
            sender_company=sender_company,
            sender_offering=sender_offering,
            value_proposition=value_proposition,
            purpose=purpose,
            tone=tone,
        )
        if ollama_res:
            return ollama_res

    # Default to rule-based generator
    return generate_email_rule_based(
        business_name=name,
        industry=industry,
        about_summary=about,
        services_offered=services,
        city=city,
        sender_company=sender_company,
        sender_offering=sender_offering,
        value_proposition=value_proposition,
        purpose=purpose,
        tone=tone,
    )


def save_email_draft(
    business_id: int,
    email_data: Dict[str, str],
    sender_company: str,
    sender_offering: str,
    outreach_status: str = "Draft Created",
    notes: str = None,
    follow_up_date = None,
) -> int:
    """Saves email draft into email_drafts table."""
    with get_db() as session:
        draft = session.query(EmailDraft).filter_by(business_id=business_id).first()
        if not draft:
            draft = EmailDraft(business_id=business_id)
            session.add(draft)

        draft.subject = email_data["subject"]
        draft.personalized_opening = email_data.get("personalized_opening")
        draft.business_context = email_data.get("business_context")
        draft.value_proposition = email_data.get("value_proposition")
        draft.call_to_action = email_data.get("call_to_action")
        draft.full_body = email_data["full_body"]
        draft.tone = email_data.get("tone", "Professional")
        draft.sender_company = sender_company
        draft.sender_offering = sender_offering
        draft.outreach_status = outreach_status
        if notes is not None:
            draft.notes = notes
        if isinstance(follow_up_date, datetime):
            draft.follow_up_date = follow_up_date
        elif isinstance(follow_up_date, date):
            draft.follow_up_date = datetime.combine(follow_up_date, datetime.min.time())

        session.flush()
        draft_id = draft.id

    log_activity(
        action="Email Draft Saved",
        target_type="email_drafts",
        target_id=draft_id,
        details=f"Draft saved for business ID {business_id} (Status: {outreach_status}).",
    )
    return draft_id
