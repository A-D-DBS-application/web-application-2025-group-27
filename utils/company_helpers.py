"""Company helper utilities - data retrieval and enrichment."""

from typing import List, Optional

from app import db
from models import Company
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
from services.competitor_filter import filter_competitors
from models import CompanyCompetitor
from sqlalchemy import or_, func
from services.competitive_landscape import generate_competitive_landscape


def get_company_industries(company: Company) -> List:
    """Get list of Industry objects for a company."""
    if not company:
        return []
    return [
        link.industry
        for link in company.industries
        if link and link.industry
    ]


def get_company_competitors(company: Company) -> List[Company]:
    """Get list of competitor Company objects."""
    if not company:
        return []
    return [
        link.competitor
        for link in company.competitors
        if link and link.competitor
    ]


def enrich_company_if_needed(company: Company, domain: Optional[str] = None) -> None:
    """Enrich company data from API if needed. Always uses OpenAI for team size, description, and funding."""
    if not company:
        return
    
    check_domain = domain or company.domain
    company_name = company.name
    company_domain = check_domain or company.domain
    
    # Fetch basic info from Company Enrich API if needed (name, website, industry, country, industries)
    # Note: fetch_company_info() will also call OpenAI for description, employees, and funding
    if check_domain and needs_api_fetch(company, check_domain):
        api_data = fetch_company_info(domain=check_domain)
        if api_data:
            # Apply ALL data including OpenAI fields (description, employees, funding)
            # apply_company_data() will always apply OpenAI fields even if they exist
            apply_company_data(company, api_data)
            link_company_industries(company, api_data.get("industries", []))
    
    # ALWAYS fetch OpenAI data for team size, description, and funding
    # This ensures we use OpenAI instead of Company Enrich for these fields, even for existing companies
    # We do this even if needs_api_fetch() returned False, to update existing companies with OpenAI data
    if company_name or company_domain:
        try:
            # Use savepoint to isolate enrichment - if it fails, only this is rolled back
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
        except Exception as e:
            # Savepoint auto-rolled back, main transaction intact
            import logging
            logging.error(f"Failed to fetch OpenAI data for {company_name or company_domain}: {e}", exc_info=True)


DEFAULT_LANDSCAPE = (
    "Competitive landscape analysis is being prepared. This section will provide "
    "insights into market positioning, competitive pressures, and strategic "
    "considerations based on available company and competitor data."
)


def refresh_competitors(company: Company) -> None:
    """Refresh competitors for a company using OpenAI.
    
    Removes all existing competitors and replaces them with OpenAI-identified competitors.
    This ensures old Company Enrich competitors are replaced with accurate OpenAI competitors.
    """
    if not company or not company.domain:
        return
    
    # Remove all existing competitor links
    db.session.query(CompanyCompetitor).filter(
        CompanyCompetitor.company_id == company.id
    ).delete()
    db.session.flush()
    
    # Fetch new competitors using OpenAI
    similar = fetch_openai_similar_companies(
        company_name=company.name,
        domain=company.domain,
        limit=10
    )
    filtered = filter_competitors(company.name, company.domain, similar)[:5]
    
    # Link new competitors
    for comp_data in filtered:
        comp_domain = comp_data.get("domain")
        if not comp_domain:
            continue
        
        comp_name = comp_data.get("name") or "Unknown"
        
        # Find or create competitor
        competitor = (
            db.session.query(Company)
            .filter(or_(
                Company.domain == comp_domain,
                func.lower(Company.name) == comp_name.lower(),
            ))
            .first()
        )
        
        if not competitor:
            competitor = Company(
                name=comp_name,
                domain=comp_domain,
                website=comp_data.get("website"),
                headline=comp_data.get("description"),
                industry=comp_data.get("industry"),
            )
            db.session.add(competitor)
            db.session.flush()
        else:
            # Update missing fields
            for field, val in [
                ("domain", comp_domain),
                ("website", comp_data.get("website")),
                ("headline", comp_data.get("description")),
                ("industry", comp_data.get("industry")),
            ]:
                if val and not getattr(competitor, field):
                    setattr(competitor, field, val)
        
        # Enrich competitor with OpenAI data (team size, description, funding)
        try:
            enrich_company_if_needed(competitor, comp_domain)
        except Exception:
            pass  # Don't fail if enrichment fails
        
        # Link competitor
        if competitor.id != company.id:
            existing_link = (
                db.session.query(CompanyCompetitor)
                .filter(
                    CompanyCompetitor.company_id == company.id,
                    CompanyCompetitor.competitor_id == competitor.id,
                )
                .first()
            )
            if not existing_link:
                db.session.add(CompanyCompetitor(
                    company_id=company.id,
                    competitor_id=competitor.id,
                ))
    
    db.session.flush()


def generate_landscape_if_needed(company: Company) -> None:
    """Generate competitive landscape if not already present."""
    if not company:
        return
    
    # Skip if already has content
    if company.competitive_landscape and company.competitive_landscape.strip():
        return
    
    competitors = get_company_competitors(company)
    if competitors:
        try:
            with db.session.begin_nested():
                landscape = generate_competitive_landscape(company, competitors)
                company.competitive_landscape = landscape if landscape else DEFAULT_LANDSCAPE
        except Exception:
            # Savepoint auto-rolled back, set default
            company.competitive_landscape = DEFAULT_LANDSCAPE
    else:
        company.competitive_landscape = DEFAULT_LANDSCAPE