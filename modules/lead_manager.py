"""
Module 5: Lead Management System.
CRUD operations, search, multi-criteria filtering, notes, and outreach tracking.
"""
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from sqlalchemy import or_, desc, asc
from database.db import get_db
from database.models import Business, LeadResearch, LeadQualification, EmailDraft
from utils.helpers import log_activity

logger = logging.getLogger("leadpilot.lead_manager")


def get_all_leads_enriched(
    search_query: str = "",
    industry_filter: str = "All",
    qualification_filter: str = "All",
    outreach_filter: str = "All",
    sort_by: str = "Score (High to Low)",
    min_score: int = 0,
) -> List[Dict[str, Any]]:
    """
    Retrieves full consolidated lead records joined with research, qualifications, and drafts.
    """
    with get_db() as session:
        query = session.query(
            Business, LeadResearch, LeadQualification, EmailDraft
        ).outerjoin(
            LeadResearch, Business.id == LeadResearch.business_id
        ).outerjoin(
            LeadQualification, Business.id == LeadQualification.business_id
        ).outerjoin(
            EmailDraft, Business.id == EmailDraft.business_id
        )

        # 1. Text Search Filter
        if search_query:
            term = f"%{search_query.strip()}%"
            query = query.filter(
                or_(
                    Business.name.ilike(term),
                    Business.normalized_domain.ilike(term),
                    Business.industry.ilike(term),
                    Business.city.ilike(term),
                    Business.country.ilike(term),
                    LeadResearch.public_email.ilike(term),
                )
            )

        # 2. Industry Filter
        if industry_filter and industry_filter != "All":
            query = query.filter(Business.industry == industry_filter)

        # 3. Qualification Status Filter
        if qualification_filter and qualification_filter != "All":
            query = query.filter(LeadQualification.qualification_status == qualification_filter)

        # 4. Outreach Status Filter
        if outreach_filter and outreach_filter != "All":
            if outreach_filter == "Not Started":
                query = query.filter(or_(EmailDraft.outreach_status == "Not Started", EmailDraft.outreach_status == None))
            else:
                query = query.filter(EmailDraft.outreach_status == outreach_filter)

        # 5. Minimum score
        if min_score and min_score > 0:
            query = query.filter(LeadQualification.lead_score >= int(min_score))

        # 6. Sorting
        if sort_by == "Score (High to Low)":
            query = query.order_by(desc(LeadQualification.lead_score).nullslast(), desc(Business.created_at))
        elif sort_by == "Score (Low to High)":
            query = query.order_by(asc(LeadQualification.lead_score).nullsfirst(), desc(Business.created_at))
        elif sort_by == "Newest First":
            query = query.order_by(desc(Business.created_at))
        elif sort_by == "Oldest First":
            query = query.order_by(asc(Business.created_at))
        elif sort_by == "Company Name (A-Z)":
            query = query.order_by(asc(Business.name))
        elif sort_by == "Company Name (Z-A)":
            query = query.order_by(desc(Business.name))

        records = _dedupe_latest_draft(query.all())

        output = []
        for biz, res, qual, draft in records:
            output.append({
                "id": biz.id,
                "name": biz.name,
                "website_url": biz.website_url,
                "normalized_domain": biz.normalized_domain,
                "industry": biz.industry or "Unspecified",
                "country": biz.country or "Unspecified",
                "city": biz.city or "",
                "business_type": biz.business_type or "",
                "description": biz.description or "",
                "discovery_source": biz.discovery_source,
                "date_discovered": biz.created_at,
                
                # Research details
                "about_summary": res.about_summary if res else "",
                "services_offered": res.services_offered if res else "",
                "public_email": res.public_email if res else None,
                "email_status": res.email_status if res else "Not found",
                "email_source_url": res.email_source_url if res else None,
                "public_phone": res.public_phone if res else None,
                "phone_status": res.phone_status if res else "Not found",
                "phone_source_url": res.phone_source_url if res else None,
                "contact_page_url": res.contact_page_url if res else None,
                "linkedin_url": res.linkedin_url if res else None,
                "crawl_status": res.crawl_status if res else "Not Researched",
                "crawled_pages_count": res.crawled_pages_count if res else 0,
                
                # Qualification details
                "lead_score": qual.lead_score if qual else 0,
                "qualification_status": qual.qualification_status if qual else "Not Qualified",
                "score_breakdown": qual.score_breakdown if qual else None,
                "missing_info": qual.missing_info if qual else None,
                "recommended_action": qual.recommended_action if qual else "Run qualification",
                "manual_override": qual.manual_override if qual else False,
                "override_reason": qual.override_reason if qual else None,
                
                # Outreach & Draft
                "draft_id": draft.id if draft else None,
                "email_subject": draft.subject if draft else None,
                "email_body": draft.full_body if draft else None,
                "email_tone": draft.tone if draft else None,
                "outreach_status": draft.outreach_status if draft else "Not Started",
                "notes": draft.notes if draft else "",
                "follow_up_date": draft.follow_up_date if draft else None,
            })

        return output


def _dedupe_latest_draft(records):
    """Keeps one row per business when more than one email draft exists."""
    chosen = {}
    order = []
    for biz, res, qual, draft in records:
        if biz.id not in chosen:
            order.append(biz.id)
            chosen[biz.id] = (biz, res, qual, draft)
            continue
        current_draft = chosen[biz.id][3]
        if draft is None:
            continue
        if current_draft is None or (draft.updated_at or datetime.min) >= (current_draft.updated_at or datetime.min):
            chosen[biz.id] = (biz, res, qual, draft)
    return [chosen[business_id] for business_id in order]


def get_lead_by_id(business_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves full details for a single lead."""
    leads = get_all_leads_enriched()
    for l in leads:
        if l["id"] == business_id:
            return l
    return None


def update_lead_details(
    business_id: int,
    name: str,
    industry: str,
    country: str,
    city: str,
    business_type: str,
    description: str,
    website_url: str,
) -> bool:
    """Updates basic business profile information."""
    with get_db() as session:
        biz = session.query(Business).filter_by(id=business_id).first()
        if not biz:
            return False
        biz.name = name
        biz.industry = industry
        biz.country = country
        biz.city = city
        biz.business_type = business_type
        biz.description = description
        biz.website_url = website_url

    log_activity(
        action="Lead Updated",
        target_type="businesses",
        target_id=business_id,
        details=f"Updated company details for '{name}'.",
    )
    return True


def update_lead_contact_info(
    business_id: int,
    email: str,
    phone: str,
    linkedin: str,
) -> bool:
    """Updates contact info in lead_research."""
    with get_db() as session:
        res = session.query(LeadResearch).filter_by(business_id=business_id).first()
        if not res:
            res = LeadResearch(business_id=business_id)
            session.add(res)
        res.public_email = email.strip() if email else None
        res.email_status = "Found" if email else "Not found"
        res.public_phone = phone.strip() if phone else None
        res.phone_status = "Found" if phone else "Not found"
        res.linkedin_url = linkedin.strip() if linkedin else None

    log_activity(
        action="Contact Details Updated",
        target_type="lead_research",
        target_id=business_id,
        details=f"Manually updated contact info (Email: {email}, Phone: {phone}).",
    )
    return True


def update_lead_outreach_status(
    business_id: int,
    outreach_status: str,
    notes: str = None,
    follow_up_date: Optional[date] = None,
) -> bool:
    """Updates outreach progression, notes, and follow up calendar."""
    with get_db() as session:
        draft = session.query(EmailDraft).filter_by(business_id=business_id).first()
        if not draft:
            draft = EmailDraft(
                business_id=business_id,
                subject="",
                full_body="",
            )
            session.add(draft)

        draft.outreach_status = outreach_status
        if notes is not None:
            draft.notes = notes
        if follow_up_date is not None:
            draft.follow_up_date = datetime.combine(follow_up_date, datetime.min.time())

    log_activity(
        action="Outreach Status Updated",
        target_type="email_drafts",
        target_id=business_id,
        details=f"Outreach status changed to '{outreach_status}'.",
    )
    return True


def delete_lead(business_id: int) -> bool:
    """Deletes a business record and cascades through research, scores, and drafts."""
    with get_db() as session:
        biz = session.query(Business).filter_by(id=business_id).first()
        if not biz:
            return False
        name = biz.name
        session.delete(biz)

    log_activity(
        action="Lead Deleted",
        target_type="businesses",
        target_id=business_id,
        details=f"Deleted business lead '{name}' and associated records.",
    )
    return True


def get_unique_industries() -> List[str]:
    """Returns sorted list of distinct industries present in database."""
    with get_db() as session:
        rows = session.query(Business.industry).filter(Business.industry != None).distinct().all()
        industries = sorted(list(set(r[0] for r in rows if r[0])))
        return industries
