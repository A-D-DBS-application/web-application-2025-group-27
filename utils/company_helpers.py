"""Helper functions for company-related operations."""

from typing import List, Optional

from app import db
from models import Company
from services.company_api import (
    fetch_company_info,
    apply_company_data,
    needs_api_fetch,
    link_company_industries
)
from services.competitive_landscape import generate_competitive_landscape


def get_company_industries(company: Company) -> List:
    """Extract industry objects from company.industries relationship.
    
    Args:
        company: Company model instance
        
    Returns:
        List of Industry objects
    """
    if not company:
        return []
    return [link.industry for link in company.industries if link and link.industry]


def get_company_competitors(company: Company) -> List[Company]:
    """Extract competitor Company objects from company.competitors relationship.
    
    Args:
        company: Company model instance
        
    Returns:
        List of Company objects (competitors)
    """
    if not company:
        return []
    return [link.competitor for link in company.competitors if link and link.competitor]


def enrich_company_if_needed(company: Company, domain: Optional[str] = None) -> None:
    """Fetch and apply company data from API if needed.
    
    Args:
        company: Company model instance
        domain: Optional domain to check against (uses company.domain if not provided)
    """
    if not company:
        return
    
    check_domain = domain or company.domain
    if check_domain and needs_api_fetch(company, check_domain):
        api_data = fetch_company_info(domain=check_domain)
        if api_data:
            apply_company_data(company, api_data)
            link_company_industries(company, api_data.get("industries", []))


def generate_landscape_if_needed(company: Company) -> None:
    """Generate competitive landscape for company if not already generated.
    
    Args:
        company: Company model instance
    """
    if not company or company.competitive_landscape:
        return
    
    competitors = get_company_competitors(company)
    if competitors:
        try:
            landscape = generate_competitive_landscape(company, competitors)
            if landscape:
                company.competitive_landscape = landscape
        except Exception:
            db.session.rollback()

