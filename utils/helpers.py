"""
UI, formatting, logging, and text-cleaning helper utilities for LeadPilot.
"""
import re
from datetime import datetime
from database.models import ActivityLog, CompanySettings
from database.db import get_db


def clean_business_name(raw_title: str) -> str:
    """
    Cleans page titles to isolate clean company names.
    Removes common suffixes like ': Home', ' | Official Website', ' - Best Agency'.
    """
    if not raw_title:
        return "Unknown Business"
        
    title = raw_title.strip()
    
    # Split on common title separators: |, -, :, •, –, —
    parts = re.split(r"\s+[|\-–—:•]\s+", title)
    if parts:
        candidate = parts[0].strip()
        # If the first part is very short or generic (like 'Home'), check subsequent
        if candidate.lower() in ("home", "welcome", "about us", "official site") and len(parts) > 1:
            candidate = parts[1].strip()
        if len(candidate) > 2:
            return candidate
            
    return title[:60]


def log_activity(action: str, target_type: str = None, target_id: int = None, details: str = None):
    """Inserts an event into the activity_logs table for audit and dashboard activity feed."""
    try:
        with get_db() as session:
            entry = ActivityLog(
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
                timestamp=datetime.utcnow(),
            )
            session.add(entry)
    except Exception as e:
        # Don't let logging break the core workflow
        print(f"Failed to write activity log: {e}")


def get_setting(key: str, default: str = "") -> str:
    """Reads one company setting. Returns default when the key is missing."""
    try:
        with get_db() as session:
            row = session.query(CompanySettings).filter_by(key=key).first()
            if row and row.value is not None:
                return row.value
    except Exception as exc:
        print(f"Failed to read setting {key}: {exc}")
    return default


def set_setting(key: str, value: str) -> None:
    """Creates or updates one company setting."""
    with get_db() as session:
        row = session.query(CompanySettings).filter_by(key=key).first()
        if not row:
            row = CompanySettings(key=key, value=value)
            session.add(row)
        else:
            row.value = value


def format_score_badge(score: int) -> str:
    """Returns color-coded badge HTML for lead score."""
    if score >= 80:
        return f'<span style="background-color:#E6F4EA;color:#137333;padding:3px 10px;border-radius:12px;font-weight:600;font-size:0.85rem;">High Priority ({score}/100)</span>'
    elif score >= 60:
        return f'<span style="background-color:#FEF7E0;color:#B06000;padding:3px 10px;border-radius:12px;font-weight:600;font-size:0.85rem;">Medium Priority ({score}/100)</span>'
    else:
        return f'<span style="background-color:#FCE8E6;color:#C5221F;padding:3px 10px;border-radius:12px;font-weight:600;font-size:0.85rem;">Low Priority ({score}/100)</span>'


def format_status_badge(status: str) -> str:
    """Returns status badge styling for outreach statuses."""
    color_map = {
        "Not Started": ("#F1F3F4", "#5F6368"),
        "Draft Created": ("#E8F0FE", "#1A73E8"),
        "Reviewed": ("#F3E8FD", "#8430CE"),
        "Ready to Send": ("#FEF7E0", "#B06000"),
        "Contacted": ("#E6F4EA", "#137333"),
    }
    bg, fg = color_map.get(status, ("#F1F3F4", "#5F6368"))
    return f'<span style="background-color:{bg};color:{fg};padding:3px 10px;border-radius:12px;font-weight:600;font-size:0.82rem;">{status}</span>'
