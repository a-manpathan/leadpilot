"""
URL, email, and phone validation and sanitization utilities.
Includes anti-SSRF protections to prevent internal-network scraping.
"""
import ipaddress
import re
import socket
from urllib.parse import urlparse
import tldextract


# Email regex (RFC 5322 compatible, clean format)
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
)

# Junk email domains or patterns to ignore
JUNK_EMAIL_PATTERNS = [
    r"example\.com$",
    r"domain\.com$",
    r"sentry\.io$",
    r"wixpress\.com$",
    r"github\.com$",
    r"test\.com$",
    r"yourdomain\.com$",
    r"email\.com$",
    r"sample\.com$",
    r"user@company\.com$",
    r"info@domain\.com$",
    r"\.(png|jpg|jpeg|gif|svg|webp|css|js)$",
]

# Phone number regex (international and local formats)
PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
)

# Blocked private and link-local IP networks (SSRF prevention)
PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def normalize_domain(url: str) -> str:
    """
    Extracts the normalized registered domain (e.g., 'example.com') from a URL or string.
    Removes protocols, ports, 'www.', query strings, and paths.
    """
    if not url:
        return ""
    
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
        
    extracted = tldextract.extract(url)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}".lower()
    
    # Fallback to urllib.parse
    parsed = urlparse(url)
    netloc = parsed.netloc.split(":")[0].lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def is_safe_url(url: str) -> tuple[bool, str]:
    """
    Validates URL safety and defends against SSRF (Server-Side Request Forgery).
    Rejects private IPs, loopback addresses, metadata endpoints, and non-HTTP schemes.
    """
    if not url:
        return False, "Empty URL"
        
    url = url.strip()
    parsed = urlparse(url)
    
    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported scheme: {parsed.scheme}"
        
    hostname = parsed.hostname
    if not hostname:
        return False, "Invalid or missing hostname"
        
    # Disallow localhost / local domains
    if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal"):
        return False, "Access to localhost or internal metadata is blocked"
        
    try:
        # Resolve hostname to check IP addresses
        addr_infos = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in addr_infos:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            for private_net in PRIVATE_NETWORKS:
                if ip_obj in private_net:
                    return False, f"Destination resolved to private IP range: {ip_str}"
    except (socket.gaierror, ValueError):
        # Could not resolve; let requests handle connection failure safely
        pass
        
    return True, "Safe"


def clean_extracted_email(email: str) -> str | None:
    """
    Sanitizes and filters an extracted email.
    Rejects dummy placeholders, image-embedded false positives, and invalid formats.
    """
    if not email:
        return None
    
    email = email.strip().lower()
    if not EMAIL_REGEX.match(email):
        return None
        
    for pattern in JUNK_EMAIL_PATTERNS:
        if re.search(pattern, email, re.IGNORECASE):
            return None
            
    # Check length and parts
    parts = email.split("@")
    if len(parts) != 2:
        return None
    user, domain = parts
    if len(user) < 2 or len(domain) < 4:
        return None
        
    return email


def clean_extracted_phone(phone: str) -> str | None:
    """
    Validates and normalizes phone number string.
    Filters out year numbers, short digit sequences, and false positives.
    """
    if not phone:
        return None
        
    digits_only = re.sub(r"\D", "", phone)
    # Most valid international and local phone numbers have between 8 and 15 digits
    if len(digits_only) < 8 or len(digits_only) > 15:
        return None
        
    # Filter repeated digits like 00000000, 11111111
    if len(set(digits_only)) <= 2:
        return None
        
    cleaned = re.sub(r"\s+", " ", phone.strip())
    return cleaned


def is_valid_linkedin_company_url(url: str) -> str | None:
    """Extracts clean LinkedIn company URL if present."""
    if not url:
        return None
    url = url.strip()
    match = re.search(r"https?://(?:www\.)?linkedin\.com/company/[a-zA-Z0-9-_]+/?", url, re.IGNORECASE)
    if match:
        return match.group(0).rstrip("/")
    return None
