"""Reporting utilities to aggregate company intelligence.

Goals
-----
- Provide a single place to assemble the data needed for weekly digest emails.
- Keep SQLAlchemy query logic out of routes/CLI code so we can reuse the same
  reporting bundle in multiple delivery channels (email, dashboards, exports).
- Return plain dictionaries that serialize cleanly to JSON or template contexts.

Reports pull from the normalized Supabase schema introduced in `models.py`,
including companies, profiles, bridge tables, and products.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from models import Company, CompanyCompetitor, CompanyIndustry, Profile, Product


@dataclass
class ReportingService:
    """Generate weekly digest reports for companies and their members.

    The service operates on a SQLAlchemy session supplied by Flask (or tests).
    Each method returns JSON-ready dictionaries so callers can dump to JSON,
    render via Jinja, or push to external channels.
    """

    session: Session

    def generate_company_weekly_report(self, company_id: str) -> Dict[str, object]:
        """Produce a summary for the given company.

        Parameters
        ----------
        company_id:
            UUID (as string or UUID object) identifying the company.

        Returns
        -------
        Dict[str, object]
            A nested structure with company metadata, member profiles,
            industries, competitors, and products.  Each entry is already cast to
            strings for UUIDs to ease JSON serialization.

        Raises
        ------
        ValueError
            When the given company does not exist.  Upstream callers should
            translate this into a 404 response or similar.

        Performance notes
        -----------------
        - Queries currently use simple filters; you can optimize later with
          eager loading if the report grows.
        - The method intentionally keeps logic straightforward so the structure
          is easy to adapt when the schema evolves.
        """

        company = self.session.query(Company).filter_by(id=company_id).first()
        if company is None:
            raise ValueError(f"Company {company_id} not found")

        profiles = self.session.query(Profile).filter_by(company_id=company_id).all()
        competitors = (
            self.session.query(CompanyCompetitor)
            .filter_by(company_id=company_id)
            .all()
        )
        industries = (
            self.session.query(CompanyIndustry)
            .filter_by(company_id=company_id)
            .all()
        )
        products = self.session.query(Product).filter_by(company_id=company_id).all()

        report = {
            "company": {
                "id": str(company.id),
                "name": company.name,
                "domain": company.domain,
                "headline": company.headline,
                "funding": company.funding,
                "employees": company.number_of_employees,
                "last_updated": company.last_updated.isoformat() if company.last_updated else None,
            },
            "profiles": [
                {
                    "id": str(profile.id),
                    "account_id": str(profile.account_id),
                    "email": profile.email,
                    "role": profile.role,
                    "phone_number": profile.phone_number,
                }
                for profile in profiles
            ],
            "industries": [
                {
                    "industry_id": str(link.industry_id),
                    "name": link.industry.name if link.industry else None,
                }
                for link in industries
            ],
            "competitors": [
                {
                    "company_id": str(link.competitor_id),
                    "name": link.competitor.name if link.competitor else None,
                    "relationship_type": link.relationship_type,
                }
                for link in competitors
            ],
            "products": [
                {
                    "id": str(product.id),
                    "name": product.name,
                    "funding": product.funding,
                    "industry": product.industry.name if product.industry else None,
                }
                for product in products
            ],
        }

        return report

    def generate_all_company_reports(self) -> List[Dict[str, object]]:
        """Generate weekly reports for every company in the system.

        Returns
        -------
        List[Dict[str, object]]
            One entry per company (delegates to
            `generate_company_weekly_report`).  Use this to feed newsletter
            batches or PDF generation tasks.

        Notes
        -----
        For large datasets you may want to stream results or process IDs in
        batches to avoid loading everything into memory at once.
        """

        company_ids = [company.id for company in self.session.query(Company.id).all()]
        return [self.generate_company_weekly_report(company_id) for company_id in company_ids]

