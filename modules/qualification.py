"""
Module 3: AI-Assisted Lead Scoring & Qualification Engine.
Transparent, rule-based 0-100 scoring based on industry, business type, services, contact availability, and geography.
"""
import json
import logging
from typing import Dict, Any, Tuple
from config.settings import SCORING_WEIGHTS, QUALIFICATION_THRESHOLDS
from database.db import get_db
from database.models import Business, LeadResearch, LeadQualification
from utils.helpers import log_activity

logger = logging.getLogger("leadpilot.qualification")


def calculate_lead_score(
    business_id: int,
    target_industry: str = "",
    target_business_type: str = "",
    target_country: str = "",
    target_city: str = "",
) -> Dict[str, Any]:
    """
    Computes a transparent 0-100 qualification score with point-by-point breakdown.
    Does not pretend to predict internal buying intent.
    """
    with get_db() as session:
        business = session.query(Business).filter_by(id=business_id).first()
        if not business:
            raise ValueError(f"Business {business_id} not found.")

        research = session.query(LeadResearch).filter_by(business_id=business_id).first()

        # Target criteria defaults to business discovery metadata if not overridden
        t_industry = (target_industry or business.industry or "").lower()
        t_btype = (target_business_type or business.business_type or "").lower()
        t_country = (target_country or business.country or "").lower()
        t_city = (target_city or business.city or "").lower()

        breakdown = {}
        missing_info = []

        # -------------------------------------------------------------
        # 1. Industry Relevance (Max: 30 pts)
        # -------------------------------------------------------------
        ind_score = 0
        b_ind = (business.industry or "").lower()
        b_desc = (business.description or "").lower()
        res_about = (research.about_summary if research and research.about_summary else "").lower()

        if t_industry and t_industry in b_ind:
            ind_score = 30
            breakdown["industry_relevance"] = {
                "points": ind_score,
                "max": 30,
                "reason": f"Exact industry match with '{business.industry}'.",
            }
        elif t_industry and (t_industry in b_desc or t_industry in res_about):
            ind_score = 22
            breakdown["industry_relevance"] = {
                "points": ind_score,
                "max": 30,
                "reason": "Industry keywords confirmed in company description or website content.",
            }
        elif b_ind:
            ind_score = 15
            breakdown["industry_relevance"] = {
                "points": ind_score,
                "max": 30,
                "reason": f"Broad industry identified: '{business.industry}'.",
            }
        else:
            missing_info.append("Industry classification is undefined.")
            breakdown["industry_relevance"] = {
                "points": 0,
                "max": 30,
                "reason": "No industry data provided.",
            }

        # -------------------------------------------------------------
        # 2. Business Type Match (Max: 25 pts)
        # -------------------------------------------------------------
        type_score = 0
        b_type = (business.business_type or "").lower()

        if t_btype and t_btype in b_type:
            type_score = 25
            breakdown["business_type_match"] = {
                "points": type_score,
                "max": 25,
                "reason": f"Target business model match: '{business.business_type}'.",
            }
        elif "b2b" in b_type or "agency" in b_type or "service" in b_type or "saas" in b_type:
            type_score = 20
            breakdown["business_type_match"] = {
                "points": type_score,
                "max": 25,
                "reason": "Standard commercial B2B business profile.",
            }
        elif b_type:
            type_score = 12
            breakdown["business_type_match"] = {
                "points": type_score,
                "max": 25,
                "reason": f"General business type: '{business.business_type}'.",
            }
        else:
            missing_info.append("Business type not verified.")
            breakdown["business_type_match"] = {
                "points": 0,
                "max": 25,
                "reason": "Business type unspecified.",
            }

        # -------------------------------------------------------------
        # 3. Website & Service Relevance (Max: 20 pts)
        # -------------------------------------------------------------
        web_score = 0
        has_services = bool(research and research.services_offered and len(research.services_offered) > 20)
        has_about = bool(research and research.about_summary and len(research.about_summary) > 20)

        if has_services and has_about:
            web_score = 20
            breakdown["website_relevance"] = {
                "points": web_score,
                "max": 20,
                "reason": "Comprehensive service offerings and verified company profile extracted.",
            }
        elif has_services or has_about:
            web_score = 14
            breakdown["website_relevance"] = {
                "points": web_score,
                "max": 20,
                "reason": "Verified active website with company description available.",
            }
        elif business.website_url:
            web_score = 6
            breakdown["website_relevance"] = {
                "points": web_score,
                "max": 20,
                "reason": "Active website discovered, but in-depth service details could not be extracted.",
            }
            missing_info.append("Deep website research not completed or access was restricted.")
        else:
            missing_info.append("No website URL available.")
            breakdown["website_relevance"] = {
                "points": 0,
                "max": 20,
                "reason": "Missing website.",
            }

        # -------------------------------------------------------------
        # 4. Available Business Contact Information (Max: 15 pts)
        # -------------------------------------------------------------
        contact_score = 0
        has_email = bool(research and research.public_email)
        has_phone = bool(research and research.public_phone)
        has_linkedin = bool(research and research.linkedin_url)

        if has_email and (has_phone or has_linkedin):
            contact_score = 15
            breakdown["contact_info"] = {
                "points": contact_score,
                "max": 15,
                "reason": f"Direct business email ({research.public_email}) and multi-channel presence (Phone/LinkedIn) found.",
            }
        elif has_email:
            contact_score = 10
            breakdown["contact_info"] = {
                "points": contact_score,
                "max": 15,
                "reason": f"Public business email found: {research.public_email}.",
            }
        elif has_phone or has_linkedin:
            contact_score = 6
            breakdown["contact_info"] = {
                "points": contact_score,
                "max": 15,
                "reason": "Phone or LinkedIn profile discovered, but direct email is missing.",
            }
            missing_info.append("Missing verified business email address.")
        else:
            missing_info.append("No public email or phone number found yet.")
            breakdown["contact_info"] = {
                "points": 0,
                "max": 15,
                "reason": "No direct contact channels extracted.",
            }

        # -------------------------------------------------------------
        # 5. Geographic Match (Max: 10 pts)
        # -------------------------------------------------------------
        geo_score = 0
        b_country = (business.country or "").lower()
        b_city = (business.city or "").lower()

        if t_city and b_city and t_city in b_city:
            geo_score = 10
            breakdown["geographic_match"] = {
                "points": geo_score,
                "max": 10,
                "reason": f"Direct city target match: '{business.city}'.",
            }
        elif t_country and b_country and t_country in b_country:
            geo_score = 8
            breakdown["geographic_match"] = {
                "points": geo_score,
                "max": 10,
                "reason": f"Country match: '{business.country}'.",
            }
        elif b_country:
            geo_score = 4
            breakdown["geographic_match"] = {
                "points": geo_score,
                "max": 10,
                "reason": f"Discovered in '{business.country}'.",
            }
        else:
            missing_info.append("Geographic location unverified.")
            breakdown["geographic_match"] = {
                "points": 0,
                "max": 10,
                "reason": "Location unknown.",
            }

        # Total Calculation
        total_score = ind_score + type_score + web_score + contact_score + geo_score
        total_score = max(0, min(100, total_score))

        # Qualification category
        if total_score >= QUALIFICATION_THRESHOLDS["high_priority"]:
            status = "High Priority"
            rec_action = "High match for ICP. Ready for customized cold outreach."
        elif total_score >= QUALIFICATION_THRESHOLDS["medium_priority"]:
            status = "Medium Priority"
            rec_action = "Good prospect. Consider enriching contact info or verifying email before sending."
        else:
            status = "Low Priority"
            rec_action = "Incomplete profile or poor ICP match. Research manually or deprioritize."

        result = {
            "business_id": business_id,
            "lead_score": total_score,
            "qualification_status": status,
            "score_breakdown": breakdown,
            "missing_info": missing_info,
            "recommended_action": rec_action,
        }

        # Check existing override while the read session is still open.
        existing_qual = session.query(LeadQualification).filter_by(business_id=business_id).first()
        if existing_qual and existing_qual.manual_override:
            result["lead_score"] = existing_qual.lead_score
            result["qualification_status"] = existing_qual.qualification_status
            result["manual_override"] = True
            result["override_reason"] = existing_qual.override_reason
            preserve_manual = True
        else:
            preserve_manual = False

    # Write in a separate transaction so SQLite is not locked by the read above.
    if not preserve_manual:
        _save_qualification(result)
    return result


def _save_qualification(data: Dict[str, Any]):
    """Persists qualification results to lead_qualifications."""
    with get_db() as session:
        qual = session.query(LeadQualification).filter_by(business_id=data["business_id"]).first()
        if not qual:
            qual = LeadQualification(business_id=data["business_id"])
            session.add(qual)

        qual.lead_score = data["lead_score"]
        qual.qualification_status = data["qualification_status"]
        qual.score_breakdown = json.dumps(data["score_breakdown"])
        qual.missing_info = json.dumps(data["missing_info"])
        qual.recommended_action = data["recommended_action"]
        qual.manual_override = data.get("manual_override", False)
        qual.override_reason = data.get("override_reason")

    log_activity(
        action="Lead Qualification",
        target_type="lead_qualifications",
        target_id=data["business_id"],
        details=f"Calculated score: {data['lead_score']}/100 ({data['qualification_status']}).",
    )


def override_lead_qualification(business_id: int, new_score: int, new_status: str, reason: str):
    """Allows manual qualification override."""
    with get_db() as session:
        qual = session.query(LeadQualification).filter_by(business_id=business_id).first()
        if not qual:
            qual = LeadQualification(business_id=business_id)
            session.add(qual)

        qual.lead_score = max(0, min(100, new_score))
        qual.qualification_status = new_status
        qual.manual_override = True
        qual.override_reason = reason

    log_activity(
        action="Manual Qualification Override",
        target_type="lead_qualifications",
        target_id=business_id,
        details=f"Manually set score to {new_score}/100 ({new_status}). Reason: {reason}",
    )
