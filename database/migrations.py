"""
Database migration and data sync utility between SQLite and Supabase PostgreSQL.
Prevents data loss during cloud deployment.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database.models import Base, Business, LeadResearch, LeadQualification, EmailDraft, ActivityLog, CompanySettings
from config.settings import PROJECT_ROOT

logger = logging.getLogger("leadpilot.migrations")


def serialize_model(instance):
    """Converts a SQLAlchemy model instance into a JSON-serializable dictionary."""
    data = {}
    for column in instance.__table__.columns:
        val = getattr(instance, column.name)
        if isinstance(val, datetime):
            data[column.name] = val.isoformat()
        else:
            data[column.name] = val
    return data


def export_database_to_json(source_db_url: str, output_path: str = None) -> str:
    """Exports all records from a source database into a portable JSON backup."""
    if output_path is None:
        backup_dir = PROJECT_ROOT / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = str(backup_dir / f"leadpilot_backup_{timestamp}.json")

    engine = create_engine(source_db_url)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        backup_data = {
            "exported_at": datetime.utcnow().isoformat(),
            "businesses": [serialize_model(b) for b in session.query(Business).all()],
            "lead_research": [serialize_model(r) for r in session.query(LeadResearch).all()],
            "lead_qualifications": [serialize_model(q) for q in session.query(LeadQualification).all()],
            "email_drafts": [serialize_model(d) for d in session.query(EmailDraft).all()],
            "activity_logs": [serialize_model(a) for a in session.query(ActivityLog).all()],
            "company_settings": [serialize_model(s) for s in session.query(CompanySettings).all()],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)

        print(f"[OK] Database exported successfully to: {output_path}")
        print(f"Total businesses exported: {len(backup_data['businesses'])}")
        return output_path
    finally:
        session.close()


def import_database_from_json(target_db_url: str, backup_file_path: str) -> bool:
    """Imports records from a JSON backup file into a target database (e.g. Supabase PostgreSQL)."""
    with open(backup_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Ensure PostgreSQL URL compatibility
    if target_db_url.startswith("postgres://"):
        target_db_url = "postgresql://" + target_db_url[len("postgres://"):]

    engine = create_engine(target_db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        def parse_dt(val):
            return datetime.fromisoformat(val) if val else None

        # 1. Import Businesses
        for b in data.get("businesses", []):
            existing = session.query(Business).filter_by(normalized_domain=b["normalized_domain"]).first()
            if not existing:
                business = Business(
                    id=b["id"],
                    name=b["name"],
                    normalized_domain=b["normalized_domain"],
                    website_url=b["website_url"],
                    industry=b.get("industry"),
                    country=b.get("country"),
                    city=b.get("city"),
                    business_type=b.get("business_type"),
                    description=b.get("description"),
                    discovery_source=b.get("discovery_source"),
                    discovery_query=b.get("discovery_query"),
                    created_at=parse_dt(b.get("created_at")),
                    updated_at=parse_dt(b.get("updated_at")),
                )
                session.add(business)
        session.commit()

        # 2. Import Lead Research
        for r in data.get("lead_research", []):
            existing = session.query(LeadResearch).filter_by(business_id=r["business_id"]).first()
            if not existing:
                research = LeadResearch(
                    id=r["id"],
                    business_id=r["business_id"],
                    about_summary=r.get("about_summary"),
                    services_offered=r.get("services_offered"),
                    public_email=r.get("public_email"),
                    email_status=r.get("email_status", "Not found"),
                    email_source_url=r.get("email_source_url"),
                    public_phone=r.get("public_phone"),
                    phone_status=r.get("phone_status", "Not found"),
                    phone_source_url=r.get("phone_source_url"),
                    contact_page_url=r.get("contact_page_url"),
                    linkedin_url=r.get("linkedin_url"),
                    crawl_status=r.get("crawl_status", "Pending"),
                    crawled_pages_count=r.get("crawled_pages_count", 0),
                    last_researched_at=parse_dt(r.get("last_researched_at")),
                )
                session.add(research)
        session.commit()

        # 3. Import Lead Qualifications
        for q in data.get("lead_qualifications", []):
            existing = session.query(LeadQualification).filter_by(business_id=q["business_id"]).first()
            if not existing:
                qual = LeadQualification(
                    id=q["id"],
                    business_id=q["business_id"],
                    lead_score=q.get("lead_score", 0),
                    qualification_status=q.get("qualification_status", "Low Priority"),
                    score_breakdown=q.get("score_breakdown"),
                    missing_info=q.get("missing_info"),
                    recommended_action=q.get("recommended_action"),
                    manual_override=q.get("manual_override", False),
                    override_reason=q.get("override_reason"),
                    updated_at=parse_dt(q.get("updated_at")),
                )
                session.add(qual)
        session.commit()

        # 4. Import Email Drafts
        for d in data.get("email_drafts", []):
            existing = session.query(EmailDraft).filter_by(id=d["id"]).first()
            if existing:
                continue
            draft = EmailDraft(
                id=d["id"],
                business_id=d["business_id"],
                subject=d["subject"],
                personalized_opening=d.get("personalized_opening"),
                business_context=d.get("business_context"),
                value_proposition=d.get("value_proposition"),
                call_to_action=d.get("call_to_action"),
                full_body=d["full_body"],
                tone=d.get("tone", "Professional"),
                sender_company=d.get("sender_company"),
                sender_offering=d.get("sender_offering"),
                outreach_status=d.get("outreach_status", "Draft Created"),
                notes=d.get("notes"),
                follow_up_date=parse_dt(d.get("follow_up_date")),
                created_at=parse_dt(d.get("created_at")),
                updated_at=parse_dt(d.get("updated_at")),
            )
            session.add(draft)
        session.commit()

        # 5. Import activity logs and company settings
        for a in data.get("activity_logs", []):
            existing = session.query(ActivityLog).filter_by(id=a["id"]).first()
            if existing:
                continue
            session.add(ActivityLog(
                id=a["id"],
                action=a["action"],
                target_type=a.get("target_type"),
                target_id=a.get("target_id"),
                details=a.get("details"),
                timestamp=parse_dt(a.get("timestamp")),
            ))
        for s in data.get("company_settings", []):
            existing = session.query(CompanySettings).filter_by(key=s["key"]).first()
            if existing:
                existing.value = s.get("value")
                continue
            session.add(CompanySettings(
                id=s["id"],
                key=s["key"],
                value=s.get("value"),
                updated_at=parse_dt(s.get("updated_at")),
            ))
        session.commit()

        if target_db_url.startswith("postgresql"):
            for table in (
                "businesses",
                "lead_research",
                "lead_qualifications",
                "email_drafts",
                "activity_logs",
                "company_settings",
            ):
                session.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 1), true)"
                ))
            session.commit()

        print(f"[OK] Successfully imported backup to target database: {target_db_url.split('@')[-1] if '@' in target_db_url else target_db_url}")
        return True
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Import failed: {e}")
        return False
    finally:
        session.close()


def sync_sqlite_to_postgres(sqlite_url: str, postgres_url: str) -> bool:
    """Convenience helper to dump SQLite and immediately hydrate PostgreSQL."""
    backup_file = export_database_to_json(sqlite_url)
    return import_database_from_json(postgres_url, backup_file)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LeadPilot Database Migration Utility")
    parser.add_argument("--export", action="store_true", help="Export local SQLite database to JSON")
    parser.add_argument("--import-file", type=str, help="Import JSON backup into target database")
    parser.add_argument("--target-url", type=str, help="Target PostgreSQL connection URL")
    
    args = parser.parse_args()
    from config.settings import DATABASE_URL
    if args.export:
        export_database_to_json(DATABASE_URL)
    elif args.import_file and args.target_url:
        import_database_from_json(args.target_url, args.import_file)
    else:
        parser.print_help()
