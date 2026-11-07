"""
Modular Search Provider abstraction.
Supports DuckDuckGo via DDGS with graceful fallback and rate-limiting resilience.
"""
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from utils.validators import normalize_domain

logger = logging.getLogger("leadpilot.search")

# Common aggregators and non-business domains to skip as primary company websites
AGGREGATOR_DOMAINS = {
    "wikipedia.org", "youtube.com", "facebook.com", "instagram.com", "twitter.com",
    "x.com", "linkedin.com", "clutch.co", "yelp.com", "yellowpages.com",
    "glassdoor.com", "indeed.com", "reddit.com", "quora.com", "pinterest.com",
    "google.com", "apple.com", "microsoft.com", "amazon.com", "medium.com",
    "goodfirms.co", "sortlist.com", "themanifest.com", "f6s.com", "g2.com",
    "capterra.com", "designrush.com", "agencyspotter.com", "upcity.com",
    "justdial.com", "indiamart.com", "sulekha.com", "ambitionbox.com",
    "crunchbase.com", "zoominfo.com", "rocketreach.co", "trustpilot.com",
    "bark.com", "thumbtack.com",
}

LISTICLE_TITLE = re.compile(
    r"(\btop\s+\d+\b|\b\d+\s+best\b|\bbest\s+\d+\b|\blist of\b|\bbest\b.+\bagenc)",
    re.IGNORECASE,
)
DIRECTORY_PATH_MARKERS = ("/blog/", "/blogs/", "/directory/", "/list/", "/top-", "/best-")


def is_directory_result(item: Dict[str, Any]) -> bool:
    """True for directories, listicles, and blog roundups rather than a company site."""
    if item.get("is_aggregator"):
        return True
    title = item.get("title") or ""
    url = (item.get("url") or "").lower()
    if LISTICLE_TITLE.search(title):
        return True
    return any(marker in url for marker in DIRECTORY_PATH_MARKERS)


class BaseSearchProvider(ABC):
    """Abstract search provider for lead discovery."""

    @abstractmethod
    def search(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """Executes a search query and returns list of results."""
        pass


class DuckDuckGoSearchProvider(BaseSearchProvider):
    """DuckDuckGo search provider using ddgs library."""

    def __init__(self, request_delay: float = 0.5):
        self.request_delay = request_delay

    def search(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        results = []
        try:
            # Try importing ddgs first, fallback to duckduckgo_search
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            logger.info(f"Executing DuckDuckGo search: '{query}', max_results={max_results}")
            with DDGS() as ddgs:
                # Query with modest page size
                raw_results = list(ddgs.text(query, max_results=max_results))
                
                for item in raw_results:
                    href = item.get("href") or item.get("link") or ""
                    title = item.get("title") or ""
                    body = item.get("body") or item.get("snippet") or ""

                    if not href or not title:
                        continue

                    domain = normalize_domain(href)
                    if not domain:
                        continue

                    results.append({
                        "title": title.strip(),
                        "url": href.strip(),
                        "domain": domain,
                        "description": body.strip(),
                        "source": "DuckDuckGo",
                        "is_aggregator": domain in AGGREGATOR_DOMAINS,
                    })
                    
            time.sleep(self.request_delay)
            return results
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed or rate-limited: {e}")
            raise


class MockSearchProvider(BaseSearchProvider):
    """Fallback provider when external free search is unavailable or rate-limited."""

    def search(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        logger.info(f"Generating realistic sample B2B leads for query: '{query}'")
        sample_pool = [
            {
                "title": "Apex Digital Growth Solutions",
                "url": "https://apexdigitalgrowth.example.com",
                "domain": "apexdigitalgrowth.example.com",
                "description": "Full-service B2B digital marketing agency specializing in lead generation, SEO, and paid performance marketing.",
                "source": "Sample/Demo Data (Search Fallback)",
                "is_aggregator": False,
            },
            {
                "title": "Nexus Enterprise Systems",
                "url": "https://nexus-enterprise.example.com",
                "domain": "nexus-enterprise.example.com",
                "description": "Cloud migration and B2B SaaS software consulting firm serving enterprise clients across North America and Europe.",
                "source": "Sample/Demo Data (Search Fallback)",
                "is_aggregator": False,
            },
            {
                "title": "Vanguard Logistics & Supply Chain",
                "url": "https://vanguardlogistics.example.com",
                "domain": "vanguardlogistics.example.com",
                "description": "Cross-border logistics, freight forwarding, and commercial supply chain solutions for manufacturers and wholesalers.",
                "source": "Sample/Demo Data (Search Fallback)",
                "is_aggregator": False,
            },
            {
                "title": "Pulse Strategic Advisory",
                "url": "https://pulsestrategic.example.com",
                "domain": "pulsestrategic.example.com",
                "description": "Management consulting, financial advisory, and business transformation services for mid-market commercial enterprises.",
                "source": "Sample/Demo Data (Search Fallback)",
                "is_aggregator": False,
            },
            {
                "title": "CyberShield Tech Defense",
                "url": "https://cybershielddef.example.com",
                "domain": "cybershielddef.example.com",
                "description": "Managed security service provider (MSSP) offering endpoint protection, compliance audits, and cloud security consulting.",
                "source": "Sample/Demo Data (Search Fallback)",
                "is_aggregator": False,
            },
        ]
        return sample_pool[:max_results]


def get_search_provider(use_mock_fallback: bool = True) -> BaseSearchProvider:
    """Factory function to get default search provider."""
    return DuckDuckGoSearchProvider()
