"""
SQLAlchemy models for LeadPilot.
Compatible with SQLite and Supabase PostgreSQL.
"""
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Business(Base):
    """Stores discovered B2B companies."""
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    normalized_domain = Column(String(255), nullable=False, unique=True, index=True)
    website_url = Column(String(500), nullable=False)
    industry = Column(String(150), nullable=True, index=True)
    country = Column(String(100), nullable=True, index=True)
    city = Column(String(100), nullable=True, index=True)
    business_type = Column(String(150), nullable=True)
    description = Column(Text, nullable=True)
    discovery_source = Column(String(100), default="DuckDuckGo Search")
    discovery_query = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    research = relationship("LeadResearch", back_populates="business", uselist=False, cascade="all, delete-orphan")
    qualification = relationship("LeadQualification", back_populates="business", uselist=False, cascade="all, delete-orphan")
    drafts = relationship("EmailDraft", back_populates="business", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Business(id={self.id}, name='{self.name}', domain='{self.normalized_domain}')>"


class LeadResearch(Base):
    """Enriched website and contact details extracted from web research."""
    __tablename__ = "lead_research"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    about_summary = Column(Text, nullable=True)
    services_offered = Column(Text, nullable=True)
    
    # Public contact details with source URLs & verification flags
    public_email = Column(String(255), nullable=True, index=True)
    email_status = Column(String(50), default="Not found")  # Found, Needs verification, Not found
    email_source_url = Column(String(500), nullable=True)
    
    public_phone = Column(String(100), nullable=True)
    phone_status = Column(String(50), default="Not found")
    phone_source_url = Column(String(500), nullable=True)
    
    contact_page_url = Column(String(500), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    
    crawl_status = Column(String(50), default="Pending")  # Pending, Completed, Partial, Blocked, Failed
    crawled_pages_count = Column(Integer, default=0)
    last_researched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    business = relationship("Business", back_populates="research")


class LeadQualification(Base):
    """Transparent AI-assisted qualification score (0-100) and breakdown."""
    __tablename__ = "lead_qualifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    lead_score = Column(Integer, default=0, nullable=False, index=True)
    qualification_status = Column(String(50), default="Low Priority", index=True)  # High Priority, Medium Priority, Low Priority
    score_breakdown = Column(Text, nullable=True)  # JSON representation of points per criterion
    missing_info = Column(Text, nullable=True)  # JSON representation of missing criteria
    recommended_action = Column(Text, nullable=True)
    
    manual_override = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    business = relationship("Business", back_populates="qualification")


class EmailDraft(Base):
    """Personalized cold outreach email drafts and lead status."""
    __tablename__ = "email_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    
    subject = Column(String(255), nullable=False)
    personalized_opening = Column(Text, nullable=True)
    business_context = Column(Text, nullable=True)
    value_proposition = Column(Text, nullable=True)
    call_to_action = Column(Text, nullable=True)
    full_body = Column(Text, nullable=False)
    tone = Column(String(50), default="Professional")
    
    sender_company = Column(String(150), nullable=True)
    sender_offering = Column(String(255), nullable=True)
    
    outreach_status = Column(String(50), default="Draft Created", index=True)  # Not Started, Draft Created, Reviewed, Ready to Send, Contacted
    notes = Column(Text, nullable=True)
    follow_up_date = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    business = relationship("Business", back_populates="drafts")


class ActivityLog(Base):
    """Audit log of discovery, research, qualification, and outreach actions."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=True)
    target_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class CompanySettings(Base):
    """User preferences, default outreach company info, and app configuration."""
    __tablename__ = "company_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
