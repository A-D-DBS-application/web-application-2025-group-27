from typing import List, Optional
from app import db
from models import Company
from services.company_api import fetch_company_info, apply_company_data, needs_api_fetch, link_company_industries
from services.competitive_landscape import generate_competitive_landscape


def get_company_industries(company: Company) -> List:
    return [link.industry for link in (company.industries if company else []) if link and link.industry]


def get_company_competitors(company: Company) -> List[Company]:
    return [link.competitor for link in (company.competitors if company else []) if link and link.competitor]


def enrich_company_if_needed(company: Company, domain: Optional[str] = None) -> None:
    if not company: return
    check_domain = domain or company.domain
    if check_domain and needs_api_fetch(company, check_domain):
        api_data = fetch_company_info(domain=check_domain)
        if api_data:
            apply_company_data(company, api_data)
            link_company_industries(company, api_data.get("industries", []))


def generate_landscape_if_needed(company: Company) -> None:
    if not company or company.competitive_landscape: return
    competitors = get_company_competitors(company)
    if competitors:
        try:
            landscape = generate_competitive_landscape(company, competitors)
            if landscape: company.competitive_landscape = landscape
        except Exception:
            db.session.rollback()
