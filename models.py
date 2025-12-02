"""Simplified database models for MVP."""

import uuid
from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID

from app import db


class User(db.Model):
    """User model - simplified from Account/Profile separation."""
    __tablename__ = "user"
    
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    company_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("company.id", ondelete="SET NULL"),
    )
    role = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    company = db.relationship("Company", back_populates="users")
    
    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class Company(db.Model):
    """Company model - simplified for MVP."""
    __tablename__ = "company"
    
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    name = db.Column(db.String(255), nullable=False, unique=True)
    domain = db.Column(db.String(255), index=True)
    website = db.Column(db.String(500))  # Full website URL
    headline = db.Column(db.Text)
    number_of_employees = db.Column(db.Integer)
    funding = db.Column(db.BigInteger)
    industry = db.Column(db.String(255))  # Legacy single industry field (kept for compatibility)
    country = db.Column(db.String(255))
    
    # Metadata
    updated_at = db.Column(db.DateTime)  # Last update timestamp from API
    competitive_landscape = db.Column(db.Text)  # AI-generated competitive landscape summary
    
    users = db.relationship("User", back_populates="company")
    competitors = db.relationship(
        "CompanyCompetitor",
        foreign_keys="CompanyCompetitor.company_id",
        back_populates="company",
    )
    industries = db.relationship(
        "CompanyIndustry",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    market_positioning = db.relationship(
        "MarketPositioning",
        back_populates="company",
        uselist=False,
        cascade="all, delete-orphan",
    )
    snapshots = db.relationship(
        "CompanySnapshot",
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="CompanySnapshot.created_at.desc()",
    )
    signals = db.relationship(
        "CompanySignal",
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="CompanySignal.created_at.desc()",
    )
    
    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"


class Industry(db.Model):
    """Industry catalogue - many companies can belong to many industries."""
    __tablename__ = "industries"
    
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text)
    
    companies = db.relationship(
        "CompanyIndustry",
        back_populates="industry",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Industry id={self.id} name={self.name!r}>"


class CompanyIndustry(db.Model):
    """Bridge table mapping companies to industries (many-to-many).
    
    Uses a composite primary key (company_id, industry_id) to allow:
    - One company to have multiple industries
    - One industry to have multiple companies
    - Preventing duplicate links between the same company and industry
    """
    __tablename__ = "company_industry"
    
    # Composite primary key: both columns together form the unique constraint
    # This allows a company to have multiple industries (many-to-many relationship)
    company_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("company.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    industry_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("industries.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    
    company = db.relationship("Company", back_populates="industries")
    industry = db.relationship("Industry", back_populates="companies")
    
    def __repr__(self) -> str:
        return f"<CompanyIndustry company_id={self.company_id} industry_id={self.industry_id}>"


class MarketPositioning(db.Model):
    """AI-generated market positioning insights for a company."""
    __tablename__ = "market_positioning"
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("company.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    value_proposition = db.Column(db.Text)
    competitive_edge = db.Column(db.Text)
    brand_perception = db.Column(db.Text)
    key_segments = db.Column(db.Text)
    weaknesses = db.Column(db.Text)
    opportunity_areas = db.Column(db.Text)
    summary = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    company = db.relationship("Company", back_populates="market_positioning")
    
    def __repr__(self) -> str:
        return f"<MarketPositioning company_id={self.company_id}>"


class CompanySnapshot(db.Model):
    """Snapshot of company data for change detection."""
    __tablename__ = "company_snapshot"
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    data = db.Column(db.Text, nullable=False)  # JSON snapshot
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    company = db.relationship("Company", back_populates="snapshots")
    
    def __repr__(self) -> str:
        return f"<CompanySnapshot company_id={self.company_id} created_at={self.created_at}>"


class CompanySignal(db.Model):
    """AI-generated signals/alerts for company changes."""
    __tablename__ = "company_signal"
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    signal_type = db.Column(db.String(64))  # headcount_change, industry_shift, etc.
    severity = db.Column(db.String(16))  # low, medium, high
    message = db.Column(db.Text)  # Short UI-ready message
    details = db.Column(db.Text)  # Longer explanation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    company = db.relationship("Company", back_populates="signals")
    
    def __repr__(self) -> str:
        return f"<CompanySignal company_id={self.company_id} type={self.signal_type}>"


class CompanyCompetitor(db.Model):
    """Simple competitor relationship - bridge table."""
    __tablename__ = "company_competitor"
    
    company_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("company.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    competitor_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("company.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    
    company = db.relationship(
        "Company",
        foreign_keys=[company_id],
        back_populates="competitors",
    )
    competitor = db.relationship(
        "Company",
        foreign_keys=[competitor_id],
    )
    
    def __repr__(self) -> str:
        return f"<CompanyCompetitor company_id={self.company_id} competitor_id={self.competitor_id}>"
