"""Database models mirroring the Supabase schema with UUID primary keys and
bridge tables for company relationships."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, DateTime, func
from sqlalchemy.dialects.postgresql import UUID

from app import db


class UUIDPrimaryKeyMixin:
    """Mixin that adds a UUID primary key column."""

    __abstract__ = True

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )


class MetadataMixin:
    """Mixin providing metadata columns to support reporting/watchdog."""

    __abstract__ = True

    created_at = db.Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_updated = db.Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    source = db.Column(db.String(255), default="Clay")


class Account(UUIDPrimaryKeyMixin, db.Model):
    """Represents an authenticated user account (one-to-one with profile)."""

    __tablename__ = "account"

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    profile = db.relationship(
        "Profile",
        uselist=False,
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Account id={self.id} email={self.email!r}>"


class Company(UUIDPrimaryKeyMixin, MetadataMixin, db.Model):
    """Company meta-data stored in the Supabase `company` table."""

    __tablename__ = "company"

    name = db.Column(db.String(255), nullable=False, unique=True)
    domain = db.Column(db.String(255), index=True)
    headline = db.Column(db.Text)
    number_of_employees = db.Column(db.BigInteger)
    funding = db.Column(db.BigInteger)
    andere_criteria = db.Column(db.Text)
    external_reference = db.Column(db.String(255))  # Clay record id / URL

    profiles = db.relationship(
        "Profile",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    industries = db.relationship(
        "CompanyIndustry",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    competitors = db.relationship(
        "CompanyCompetitor",
        foreign_keys="CompanyCompetitor.company_id",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    is_competitor_for = db.relationship(
        "CompanyCompetitor",
        foreign_keys="CompanyCompetitor.competitor_id",
        back_populates="competitor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    products = db.relationship(
        "Product",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"


class Industry(UUIDPrimaryKeyMixin, MetadataMixin, db.Model):
    """Industry catalogue stored in the `industries` table."""

    __tablename__ = "industries"

    name = db.Column(db.String(255), nullable=False, unique=True)
    value = db.Column(db.BigInteger)
    description = db.Column(db.Text)

    companies = db.relationship(
        "CompanyIndustry",
        back_populates="industry",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Industry id={self.id} name={self.name!r}>"


class Profile(UUIDPrimaryKeyMixin, db.Model):
    """User profile enriched with manual inputs and Clay-sourced data."""

    __tablename__ = "profile"

    account_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    company_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("company.id", ondelete="SET NULL"),
    )
    email = db.Column(db.String(255), nullable=False, index=True)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(255))
    phone_number = db.Column(db.String(32))
    date_of_birth = db.Column(db.Date)
    country = db.Column(db.String(120))

    account = db.relationship("Account", back_populates="profile")
    company = db.relationship("Company", back_populates="profiles")

    def __repr__(self) -> str:
        return f"<Profile id={self.id} email={self.email!r} company_id={self.company_id}>"


class CompanyCompetitor(db.Model):
    """Self-referencing bridge table mapping company competition relationships."""

    __tablename__ = "company_competitor"
    __table_args__ = (
        db.PrimaryKeyConstraint("company_id", "competitor_id", name="company_competitor_pk"),
        CheckConstraint("company_id <> competitor_id", name="ck_company_not_self"),
    )

    company_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("company.id", ondelete="CASCADE"),
        nullable=False,
    )
    competitor_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("company.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type = db.Column(db.String(255))
    notes = db.Column(db.Text)

    company = db.relationship(
        "Company",
        foreign_keys=[company_id],
        back_populates="competitors",
    )
    competitor = db.relationship(
        "Company",
        foreign_keys=[competitor_id],
        back_populates="is_competitor_for",
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyCompetitor company_id={self.company_id} "
            f"competitor_id={self.competitor_id} relationship={self.relationship_type!r}>"
        )


class CompanyIndustry(db.Model):
    """Bridge table mapping companies to industries."""

    __tablename__ = "company_industry"
    __table_args__ = (
        db.PrimaryKeyConstraint("company_id", "industry_id", name="company_industry_pk"),
    )

    company_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("company.id", ondelete="CASCADE"),
        nullable=False,
    )
    industry_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("industries.id", ondelete="CASCADE"),
        nullable=False,
    )

    company = db.relationship("Company", back_populates="industries")
    industry = db.relationship("Industry", back_populates="companies")

    def __repr__(self) -> str:
        return f"<CompanyIndustry company_id={self.company_id} industry_id={self.industry_id}>"


class Product(UUIDPrimaryKeyMixin, MetadataMixin, db.Model):
    """Optional product-level entity scoped to a company and optionally an industry."""

    __tablename__ = "product"

    company_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("company.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = db.Column(db.String(255), nullable=False)
    industry_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("industries.id", ondelete="SET NULL"),
    )
    funding = db.Column(db.BigInteger)
    description = db.Column(db.Text)

    company = db.relationship("Company", back_populates="products")
    industry = db.relationship("Industry")

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name!r} company_id={self.company_id}>"