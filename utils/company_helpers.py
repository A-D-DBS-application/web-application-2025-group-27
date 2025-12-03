"""Company helper utilities - data retrieval and enrichment."""

import logging
from typing import List, Optional

from sqlalchemy import func, or_

from app import db
from models import Company, CompanyCompetitor
from services.company_api import (
    apply_company_data,
    fetch_company_info,
    fetch_openai_description,
    fetch_openai_funding,
    fetch_openai_similar_companies,
    fetch_openai_team_size,
    link_company_industries,
    needs_api_fetch,
)
from services.competitive_landscape import generate_competitive_landscape


logger = logging.getLogger(__name__)


def _collect_related(company, relation: str, attr: str):
    return [] if not company else [
        getattr(link, attr) for link in getattr(company, relation, []) or [] if link and getattr(link, attr)
    ]


def get_company_industries(company: Company) -> List:
    """Get list of Industry objects for a company."""
    return _collect_related(company, "industries", "industry")


def get_company_competitors(company: Company) -> List[Company]:
    """Get list of competitor Company objects."""
    return _collect_related(company, "competitors", "competitor")


def _apply_company_enrich(company: Company, domain: Optional[str]) -> None:
    if not domain or not needs_api_fetch(company, domain):
        return
    api_data = fetch_company_info(domain=domain)
    if api_data:
        apply_company_data(company, api_data)
        link_company_industries(company, api_data.get("industries", []))


def _apply_openai_overrides(company: Company, company_name: Optional[str], company_domain: Optional[str]) -> None:
    if not (company_name or company_domain):
        return
    originals = (
        company.number_of_employees,
        company.headline,
        company.funding,
    )
    try:
        with db.session.begin_nested():
            team_size = fetch_openai_team_size(company_name=company_name, domain=company_domain)
            if team_size is not None:
                company.number_of_employees = team_size
            description = fetch_openai_description(company_name=company_name, domain=company_domain)
            if description:
                company.headline = description
            funding = fetch_openai_funding(company_name=company_name, domain=company_domain)
            if funding is not None:
                company.funding = funding
    except Exception as exc:
        company.number_of_employees, company.headline, company.funding = originals
        logger.error("Failed to fetch OpenAI data for %s: %s", company_name or company_domain, exc, exc_info=True)


def enrich_company_if_needed(company: Company, domain: Optional[str] = None) -> None:
    """Enrich company data from API if needed. Always uses OpenAI for team size, description, and funding."""
    if not company:
        return
    target_domain = domain or company.domain
    _apply_company_enrich(company, target_domain)
    _apply_openai_overrides(company, company.name, target_domain or company.domain)


DEFAULT_LANDSCAPE = (
    "Competitive landscape analysis is being prepared. This section will provide "
    "insights into market positioning, competitive pressures, and strategic "
    "considerations based on available company and competitor data."
)


def _upsert_competitor(comp_data: dict) -> Optional[Company]:
    """Find or create a competitor Company from API data."""
    comp_domain = comp_data.get("domain")
    if not comp_domain:
        return None
    comp_name = comp_data.get("name") or "Unknown"
    competitor = db.session.query(Company).filter(or_(
        Company.domain == comp_domain, func.lower(Company.name) == comp_name.lower()
    )).first()
    if not competitor:
        competitor = Company()
        competitor.name = comp_name
        competitor.domain = comp_domain
        competitor.website = comp_data.get("website")
        competitor.headline = comp_data.get("description")
        competitor.industry = comp_data.get("industry")
        db.session.add(competitor)
        db.session.flush()
    else:
        for field, val in [("domain", comp_domain), ("website", comp_data.get("website")),
                           ("headline", comp_data.get("description")), ("industry", comp_data.get("industry"))]:
            if val and not getattr(competitor, field):
                setattr(competitor, field, val)
    return competitor


def _ensure_competitor_link(company: Company, competitor: Company) -> None:
    """Link company to competitor if not already linked."""
    if not company or not competitor or competitor.id == company.id:
        return
    exists = db.session.query(CompanyCompetitor).filter(
        CompanyCompetitor.company_id == company.id, CompanyCompetitor.competitor_id == competitor.id
    ).first()
    if not exists:
        link = CompanyCompetitor()
        link.company_id = company.id
        link.competitor_id = competitor.id
        db.session.add(link)


def add_competitor_from_data(company: Company, comp_data: dict) -> Optional[Company]:
    """Add competitor relationship from API payload."""
    competitor = _upsert_competitor(comp_data)
    if not competitor:
        return None
    try:
        enrich_company_if_needed(competitor, comp_data.get("domain"))
    except Exception as exc:
        logger.error("Failed to enrich competitor %s: %s", competitor.name, exc, exc_info=True)
    _ensure_competitor_link(company, competitor)
    return competitor


def refresh_competitors(company: Company) -> None:
    """Replace competitor links with fresh OpenAI results."""
    if not company or not company.domain:
        return
    db.session.query(CompanyCompetitor).filter(CompanyCompetitor.company_id == company.id).delete()
    db.session.flush()
    similar = fetch_openai_similar_companies(company_name=company.name, domain=company.domain, limit=10)
    base_domain = (company.domain or "").lower().strip()
    for comp_data in similar[:5]:
        comp_domain = (comp_data.get("domain") or "").lower().strip()
        if not comp_domain or comp_domain == base_domain:
            continue
        add_competitor_from_data(company, comp_data)


def generate_landscape_if_needed(company: Company) -> None:
    """Generate competitive landscape if not already present."""
    if not company or (company.competitive_landscape or "").strip():
        return
    competitors = get_company_competitors(company)
    if not competitors:
        company.competitive_landscape = DEFAULT_LANDSCAPE
        return
    try:
        with db.session.begin_nested():
            company.competitive_landscape = generate_competitive_landscape(company, competitors) or DEFAULT_LANDSCAPE
    except Exception:
        company.competitive_landscape = DEFAULT_LANDSCAPE