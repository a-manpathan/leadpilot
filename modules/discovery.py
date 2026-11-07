"""
Module 1: Business Discovery Engine.
Generates targeted queries, executes search, deduplicates by domain, and persists leads.
"""
import logging
from typing import List, Dict, Any, Tuple
from database.db import get_db
from database.models import Business
from utils.search import DuckDuckGoSearchProvider, MockSearchProvider, is_directory_result
from utils.validators import normalize_domain
from utils.helpers import clean_business_name, log_activity

logger = logging.getLogger("leadpilot.discovery")


def generate_search_queries(
    industry: str,
    country: str,
    city: str = "",
    business_type: str = "",
) -> List[str]:
    """Generates a list of targeted B2B discovery queries."""
    queries = []
    location_parts = [p.strip() for p in [city, country] if p.strip()]
    location_str = " ".join(location_parts)

    # Primary query
    if location_str:
        queries.append(f"{industry} companies in {location_str}")
        if business_type:
            queries.append(f"{business_type} {industry} {location_str}")
        queries.append(f"top {industry} {location_str} official website")
    else:
        queries.append(f"{industry} companies")
        if business_type:
            queries.append(f"{business_type} {industry}")
        queries.append(f"top {industry} official website")

    return queries


def discover_businesses(
    industry: str,
    country: str,
    city: str = "",
    business_type: str = "",
    max_results: int = 20,
    skip_aggregators: bool = True,
    search_provider: Any = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Executes search across queries, deduplicates by domain, and returns clean prospects.
    Falls back gracefully to MockSearchProvider if free search is throttled or offline.
    """
    if search_provider is None:
        search_provider = DuckDuckGoSearchProvider()

    queries = generate_search_queries(industry, country, city, business_type)
    discovered_leads: List[Dict[str, Any]] = []
    seen_domains = set()

    # Preload existing domains in DB to prevent duplicates
    with get_db() as session:
        existing_db_domains = set(
            d[0] for d in session.query(Business.normalized_domain).all()
        )

    stats = {
        "queries_run": 0,
        "raw_results_found": 0,
        "aggregators_skipped": 0,
        "already_in_db": 0,
        "duplicates_in_run": 0,
        "new_leads_ready": 0,
        "fallback_used": False,
    }

    # Execute search queries
    for query in queries:
        if len(discovered_leads) >= max_results:
            break

        stats["queries_run"] += 1
        raw_items = []

        try:
            raw_items = search_provider.search(query, max_results=max_results)
        except Exception as e:
            logger.warning(f"Primary search failed on query '{query}': {e}. Triggering fallback provider.")
            stats["fallback_used"] = True
            mock_provider = MockSearchProvider()
            raw_items = mock_provider.search(query, max_results=max_results)

        stats["raw_results_found"] += len(raw_items)

        for item in raw_items:
            domain = item["domain"]

            # Filter directories, listicles, and known aggregator sites.
            if skip_aggregators and is_directory_result(item):
                stats["aggregators_skipped"] += 1
                continue

            # Deduplicate against current run
            if domain in seen_domains:
                stats["duplicates_in_run"] += 1
                continue

            seen_domains.add(domain)

            # Check if already in database
            is_existing = domain in existing_db_domains
            if is_existing:
                stats["already_in_db"] += 1

            business_name = clean_business_name(item["title"])

            discovered_leads.append({
                "name": business_name,
                "website_url": item["url"],
                "normalized_domain": domain,
                "industry": industry,
                "country": country,
                "city": city if city else None,
                "business_type": business_type if business_type else "B2B Business",
                "description": item["description"],
                "discovery_source": item["source"],
                "discovery_query": query,
                "already_in_db": is_existing,
            })

            if len(discovered_leads) >= max_results:
                break

    stats["new_leads_ready"] = len([l for l in discovered_leads if not l["already_in_db"]])
    return discovered_leads, stats


def save_discovered_leads(leads: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Saves new discovered leads into the database.
    Returns (saved_count, skipped_count).
    """
    saved_count = 0
    skipped_count = 0

    with get_db() as session:
        for lead in leads:
            existing = session.query(Business).filter_by(normalized_domain=lead["normalized_domain"]).first()
            if existing:
                skipped_count += 1
                continue

            business = Business(
                name=lead["name"],
                normalized_domain=lead["normalized_domain"],
                website_url=lead["website_url"],
                industry=lead.get("industry"),
                country=lead.get("country"),
                city=lead.get("city"),
                business_type=lead.get("business_type"),
                description=lead.get("description"),
                discovery_source=lead.get("discovery_source", "DuckDuckGo"),
                discovery_query=lead.get("discovery_query"),
            )
            session.add(business)
            saved_count += 1

    if saved_count > 0:
        log_activity(
            action="Business Discovery",
            target_type="businesses",
            details=f"Discovered and saved {saved_count} new business records ({skipped_count} skipped as duplicates).",
        )

    return saved_count, skipped_count
