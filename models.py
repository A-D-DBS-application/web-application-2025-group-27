"""Vereenvoudigde database modellen voor MVP."""

import uuid
from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID

from app import db


class User(db.Model):
    """Gebruikersmodel - vereenvoudigd van Account/Profile scheiding.
    
    Elke gebruiker hoort bij één company (via company_id). Als de company
    verwijderd wordt, wordt company_id op NULL gezet (SET NULL).
    """
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
    """Bedrijfsmodel - vereenvoudigd voor MVP.
    
    Company is self-referential: een company kan zowel "main company" zijn
    (die anderen trackt) als "competitor" zijn (die getrackt wordt door anderen).
    Dit wordt gehandhaafd via CompanyCompetitor relaties.
    """
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
    industry = db.Column(db.String(255))  # Legacy single industry veld (behouden voor compatibiliteit)
    country = db.Column(db.String(255))
    
    # Metadata
    updated_at = db.Column(db.DateTime)  # Laatste update timestamp van API
    competitive_landscape = db.Column(db.Text)  # AI-gegenereerde competitive landscape samenvatting
    
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
    snapshots = db.relationship(
        "CompanySnapshot",
        foreign_keys="CompanySnapshot.company_id",
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="CompanySnapshot.created_at.desc()",
    )
    signals = db.relationship(
        "CompanySignal",
        foreign_keys="CompanySignal.company_id",
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="CompanySignal.created_at.desc()",
    )
    
    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"


class Industry(db.Model):
    """Industrie catalogus - many-to-many relatie met companies.
    
    Via CompanyIndustry kunnen companies meerdere industries hebben
    en industries kunnen meerdere companies bevatten.
    """
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
    """Bridge tabel die companies aan industries koppelt (many-to-many).
    
    Gebruikt een composite primary key (company_id, industry_id) om te zorgen dat:
    - Een company meerdere industries kan hebben
    - Een industry meerdere companies kan bevatten
    - Duplicate links tussen dezelfde company en industry voorkomen worden
    """
    __tablename__ = "company_industry"
    
    # Composite primary key: beide kolommen vormen samen de unique constraint
    # Dit maakt many-to-many relatie mogelijk zonder extra unique index
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


class CompanySnapshot(db.Model):
    """Snapshot van competitor data voor change detection.
    
    KRITIEK: Snapshots worden ALLEEN gemaakt voor COMPETITORS, nooit voor het main company.
    Dit wordt gehandhaafd in services/signals.py - alleen _iter_competitors() wordt gebruikt.
    """
    __tablename__ = "company_snapshot"
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    competitor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("company.id", ondelete="CASCADE"), nullable=True)
    data = db.Column(db.Text, nullable=False)  # JSON snapshot met basic, organization, hiring_focus, strategic_profile
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    company = db.relationship("Company", foreign_keys=[company_id], back_populates="snapshots")
    competitor = db.relationship("Company", foreign_keys=[competitor_id])
    
    def __repr__(self) -> str:
        return f"<CompanySnapshot company_id={self.company_id} competitor_id={self.competitor_id}>"


class CompanySignal(db.Model):
    """AI-gegenereerde signals/alerts voor COMPETITOR veranderingen.
    
    KRITIEK: Signals worden ALLEEN gegenereerd voor competitors, nooit voor het main company.
    Dit wordt gehandhaafd via _competitor_signal_query() die competitor_id.isnot(None) filtert.
    """
    __tablename__ = "company_signal"
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("company.id", ondelete="CASCADE"), nullable=False)
    competitor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("company.id", ondelete="CASCADE"), nullable=True)
    signal_type = db.Column(db.String(64))  # headcount_change, industry_shift, hiring_shift, market_expansion, etc.
    category = db.Column(db.String(32))  # hiring, product, funding (enforced via _force_category_from_signal_type)
    severity = db.Column(db.String(16))  # low, medium, high (gebaseerd op competitieve impact)
    message = db.Column(db.Text)  # Korte UI-ready message
    details = db.Column(db.Text)  # Langere uitleg (kan JSON bevatten met related_news)
    source_url = db.Column(db.Text)  # URL naar bron (nieuwsartikel, company pagina, etc.)
    is_new = db.Column(db.Boolean, default=True, nullable=False)  # Unread tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    company = db.relationship("Company", foreign_keys=[company_id], back_populates="signals")
    competitor = db.relationship("Company", foreign_keys=[competitor_id])
    
    def __repr__(self) -> str:
        return f"<CompanySignal company_id={self.company_id} competitor_id={self.competitor_id} type={self.signal_type}>"


class CompanyCompetitor(db.Model):
    """Eenvoudige competitor relatie - bridge tabel.
    
    Composite primary key voorkomt duplicate links. CASCADE delete zorgt
    dat competitor links verwijderd worden als company of competitor verwijderd wordt.
    """
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
