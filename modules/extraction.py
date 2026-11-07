"""
Module 2: Website and Contact Research Engine.
Crawls business websites responsibly, extracts public business info, and tracks source URLs.
"""
import logging
import re
import time
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

from config.settings import (
    DEFAULT_USER_AGENT,
    HTTP_TIMEOUT_SECONDS,
    MAX_CRAWL_PAGES_PER_SITE,
    REQUEST_DELAY_SECONDS,
    CONTACT_STATUS_FOUND,
    CONTACT_STATUS_NEEDS_VERIFICATION,
    CONTACT_STATUS_NOT_FOUND,
)
from database.db import get_db
from database.models import Business, LeadResearch
from utils.validators import (
    is_safe_url,
    normalize_domain,
    clean_extracted_email,
    clean_extracted_phone,
    is_valid_linkedin_company_url,
    EMAIL_REGEX,
    PHONE_REGEX,
)
from utils.helpers import log_activity

logger = logging.getLogger("leadpilot.extraction")

# Keywords for locating relevant subpages
ABOUT_KEYWORDS = ["about", "about-us", "who-we-are", "company", "our-story"]
CONTACT_KEYWORDS = ["contact", "contact-us", "get-in-touch", "reach-us"]
SERVICES_KEYWORDS = ["services", "what-we-do", "solutions", "offerings", "products"]


def fetch_page_safely(url: str, timeout: int = HTTP_TIMEOUT_SECONDS) -> Optional[requests.Response]:
    """Safely fetches a webpage with SSRF prevention and standard browser headers."""
    is_safe, reason = is_safe_url(url)
    if not is_safe:
        logger.warning(f"Blocked unsafe URL '{url}': {reason}")
        return None

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            verify=True,
        )
        # Content-type check: only process HTML
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            logger.info(f"Skipping non-HTML resource: {content_type} from {url}")
            return None

        if response.status_code == 200:
            return response
        else:
            logger.warning(f"HTTP {response.status_code} received from {url}")
            return None
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error fetching {url}: {e}")
        return None


def extract_meta_description(soup: BeautifulSoup) -> str:
    """Extracts meta description or OpenGraph description from HTML soup."""
    meta = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta and meta.get("content"):
        return meta["content"].strip()

    og_desc = soup.find("meta", attrs={"property": re.compile(r"^og:description$", re.I)})
    if og_desc and og_desc.get("content"):
        return og_desc["content"].strip()

    return ""


def find_candidate_links(soup: BeautifulSoup, base_url: str, target_domain: str) -> Dict[str, str]:
    """Finds candidate subpage URLs on the same domain for About, Contact, and Services."""
    discovered = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        # Ensure it stays on the same registered domain
        if normalize_domain(parsed.netloc) != target_domain:
            continue

        path_lower = parsed.path.lower()
        if not path_lower or path_lower == "/":
            continue

        if "about" not in discovered and any(k in path_lower for k in ABOUT_KEYWORDS):
            discovered["about"] = full_url
        elif "contact" not in discovered and any(k in path_lower for k in CONTACT_KEYWORDS):
            discovered["contact"] = full_url
        elif "services" not in discovered and any(k in path_lower for k in SERVICES_KEYWORDS):
            discovered["services"] = full_url

        if len(discovered) >= 3:
            break

    return discovered


def extract_emails_from_page(soup: BeautifulSoup, page_url: str, business_domain: str) -> List[Dict[str, Any]]:
    """Extracts emails from mailto links and page text with source attribution."""
    found_emails = []
    seen = set()

    # 1. First priority: mailto links (highest confidence)
    for a in soup.find_all("a", href=re.compile(r"^mailto:", re.I)):
        raw = a["href"].replace("mailto:", "").split("?")[0].strip()
        cleaned = clean_extracted_email(raw)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            # If domain matches company, status is 'Found', otherwise 'Needs verification'
            status = CONTACT_STATUS_FOUND if business_domain in cleaned else CONTACT_STATUS_NEEDS_VERIFICATION
            found_emails.append({
                "email": cleaned,
                "status": status,
                "source_url": page_url,
            })

    # 2. Second priority: visible text regex
    text = soup.get_text(separator=" ", strip=True)
    raw_matches = EMAIL_REGEX.findall(text)
    for raw in raw_matches:
        cleaned = clean_extracted_email(raw)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            status = CONTACT_STATUS_FOUND if business_domain in cleaned else CONTACT_STATUS_NEEDS_VERIFICATION
            found_emails.append({
                "email": cleaned,
                "status": status,
                "source_url": page_url,
            })

    return found_emails


def extract_phones_from_page(soup: BeautifulSoup, page_url: str) -> List[Dict[str, Any]]:
    """Extracts phone numbers from tel links and page text."""
    found_phones = []
    seen = set()

    # 1. tel: links
    for a in soup.find_all("a", href=re.compile(r"^tel:", re.I)):
        raw = a["href"].replace("tel:", "").strip()
        cleaned = clean_extracted_phone(raw)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            found_phones.append({
                "phone": cleaned,
                "status": CONTACT_STATUS_FOUND,
                "source_url": page_url,
            })

    # 2. Regex scan on text
    text = soup.get_text(separator=" ", strip=True)
    matches = PHONE_REGEX.findall(text)
    for raw in matches:
        cleaned = clean_extracted_phone(raw)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            found_phones.append({
                "phone": cleaned,
                "status": CONTACT_STATUS_NEEDS_VERIFICATION,
                "source_url": page_url,
            })
            if len(found_phones) >= 3:
                break

    return found_phones


def extract_social_links(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    """Extracts LinkedIn company link if present."""
    socials = {"linkedin": None}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        li = is_valid_linkedin_company_url(href)
        if li:
            socials["linkedin"] = li
            break
    return socials


def extract_section_text(soup: BeautifulSoup, keywords: List[str], max_len: int = 500) -> str:
    """Extracts text from paragraphs or sections matching keywords."""
    for tag in soup.find_all(["section", "div", "article", "p"]):
        id_class = f"{tag.get('id', '')} {' '.join(tag.get('class', []))}".lower()
        if any(k in id_class for k in keywords):
            text = tag.get_text(separator=" ", strip=True)
            if len(text) > 40:
                return text[:max_len]
    return ""


def research_business(business_id: int) -> Dict[str, Any]:
    """
    Crawls and enriches a single business website.
    Visits homepage and up to (MAX_CRAWL_PAGES_PER_SITE - 1) relevant subpages.
    Saves results to the lead_research table.
    """
    with get_db() as session:
        business = session.query(Business).filter_by(id=business_id).first()
        if not business:
            raise ValueError(f"Business with id {business_id} not found.")

        target_url = business.website_url
        target_domain = business.normalized_domain

    result = {
        "business_id": business_id,
        "website_url": target_url,
        "about_summary": "",
        "services_offered": "",
        "public_email": None,
        "email_status": CONTACT_STATUS_NOT_FOUND,
        "email_source_url": None,
        "public_phone": None,
        "phone_status": CONTACT_STATUS_NOT_FOUND,
        "phone_source_url": None,
        "contact_page_url": None,
        "linkedin_url": None,
        "crawl_status": "Completed",
        "crawled_pages_count": 0,
    }

    # Fetch homepage
    home_resp = fetch_page_safely(target_url)
    if not home_resp:
        result["crawl_status"] = "Blocked" if home_resp is None else "Failed"
        _save_research_result(result)
        return result

    result["crawled_pages_count"] = 1
    home_soup = BeautifulSoup(home_resp.text, "html.parser")

    # Meta description as initial about summary
    meta_desc = extract_meta_description(home_soup)
    if meta_desc:
        result["about_summary"] = meta_desc

    # Social links
    socials = extract_social_links(home_soup)
    result["linkedin_url"] = socials["linkedin"]

    # Extract contacts from homepage
    all_emails = extract_emails_from_page(home_soup, target_url, target_domain)
    all_phones = extract_phones_from_page(home_soup, target_url)

    # Services from homepage if available
    services_text = extract_section_text(home_soup, SERVICES_KEYWORDS, max_len=400)
    if services_text:
        result["services_offered"] = services_text

    # Discover candidate subpages
    subpages = find_candidate_links(home_soup, target_url, target_domain)
    pages_to_crawl = list(subpages.items())[: MAX_CRAWL_PAGES_PER_SITE - 1]

    # Crawl discovered subpages sequentially with delay
    for page_type, sub_url in pages_to_crawl:
        time.sleep(REQUEST_DELAY_SECONDS)
        sub_resp = fetch_page_safely(sub_url)
        if not sub_resp:
            continue

        result["crawled_pages_count"] += 1
        sub_soup = BeautifulSoup(sub_resp.text, "html.parser")

        # Extract contacts
        sub_emails = extract_emails_from_page(sub_soup, sub_url, target_domain)
        all_emails.extend(sub_emails)

        sub_phones = extract_phones_from_page(sub_soup, sub_url)
        all_phones.extend(sub_phones)

        # Page-specific enrichment
        if page_type == "contact":
            result["contact_page_url"] = sub_url
        elif page_type == "about" and (not result["about_summary"] or len(result["about_summary"]) < 100):
            about_p = sub_soup.find("p")
            if about_p:
                result["about_summary"] = about_p.get_text(strip=True)[:500]
        elif page_type == "services" and not result["services_offered"]:
            services_p = sub_soup.find("p")
            if services_p:
                result["services_offered"] = services_p.get_text(strip=True)[:400]

        # Socials from subpage if not found on home
        if not result["linkedin_url"]:
            sub_socials = extract_social_links(sub_soup)
            if sub_socials["linkedin"]:
                result["linkedin_url"] = sub_socials["linkedin"]

    # Select best email
    if all_emails:
        # Prioritize 'Found' over 'Needs verification'
        all_emails.sort(key=lambda e: 0 if e["status"] == CONTACT_STATUS_FOUND else 1)
        best_email = all_emails[0]
        result["public_email"] = best_email["email"]
        result["email_status"] = best_email["status"]
        result["email_source_url"] = best_email["source_url"]

    # Select best phone
    if all_phones:
        all_phones.sort(key=lambda p: 0 if p["status"] == CONTACT_STATUS_FOUND else 1)
        best_phone = all_phones[0]
        result["public_phone"] = best_phone["phone"]
        result["phone_status"] = best_phone["status"]
        result["phone_source_url"] = best_phone["source_url"]

    _save_research_result(result)
    return result


def _save_research_result(data: Dict[str, Any]):
    """Persists research results into the database."""
    with get_db() as session:
        research = session.query(LeadResearch).filter_by(business_id=data["business_id"]).first()
        if not research:
            research = LeadResearch(business_id=data["business_id"])
            session.add(research)

        research.about_summary = data.get("about_summary")
        research.services_offered = data.get("services_offered")
        research.public_email = data.get("public_email")
        research.email_status = data.get("email_status", CONTACT_STATUS_NOT_FOUND)
        research.email_source_url = data.get("email_source_url")
        research.public_phone = data.get("public_phone")
        research.phone_status = data.get("phone_status", CONTACT_STATUS_NOT_FOUND)
        research.phone_source_url = data.get("phone_source_url")
        research.contact_page_url = data.get("contact_page_url")
        research.linkedin_url = data.get("linkedin_url")
        research.crawl_status = data.get("crawl_status", "Completed")
        research.crawled_pages_count = data.get("crawled_pages_count", 0)

    log_activity(
        action="Website Research",
        target_type="lead_research",
        target_id=data["business_id"],
        details=f"Researched website. Crawl status: {data.get('crawl_status')}. Email: {data.get('email_status')}. Phone: {data.get('phone_status')}.",
    )
