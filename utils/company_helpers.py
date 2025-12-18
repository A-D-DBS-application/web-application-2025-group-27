"""Helperfuncties voor company-data: ophalen, enrichment en relaties."""

import logging
from typing import List, Optional

from sqlalchemy import func, or_

from app import db
from models import Company, CompanyCompetitor
from services.competitive_landscape import generate_competitive_landscape
from services.company_api import (
    fetch_openai_description,
    fetch_openai_funding,
    fetch_openai_similar_companies,
    fetch_openai_team_size,
)


logger = logging.getLogger(__name__)


def _collect_related(company, relation: str, attr: str):
    """Helper om gerelateerde objecten op te halen via een relation naam.
    
    Gebruikt door get_company_industries en get_company_competitors om
    de juiste objecten uit de many-to-many relaties te halen.
    """
    return [] if not company else [
        getattr(link, attr) for link in getattr(company, relation, []) or [] if link and getattr(link, attr)
    ]


def get_company_industries(company: Company) -> List:
    """Haal lijst van Industry objecten op voor een company."""
    return _collect_related(company, "industries", "industry")


def get_company_competitors(company: Company) -> List[Company]:
    """Haal lijst van competitor Company objecten op."""
    return _collect_related(company, "competitors", "competitor")


def _apply_openai_overrides(company: Company, company_name: Optional[str], company_domain: Optional[str], use_web_search: bool = False) -> None:
    """Pas OpenAI data toe op company velden (team size, beschrijving, funding).
    
    KRITIEK: OpenAI data krijgt ALTIJD voorrang - dit overschrijft bestaande waarden.
    Dit is bewust: OpenAI data is accurater dan handmatig ingevoerde data.
    Als OpenAI call faalt, worden originele waarden hersteld via nested transaction rollback.
    
    Args:
        use_web_search: Als True, gebruik web search (langzamer). Standaard False voor performance.
    """
    if not (company_name or company_domain):
        return
    originals = (
        company.number_of_employees,
        company.headline,
        company.funding,
    )
    try:
        with db.session.begin_nested():
            team_size = fetch_openai_team_size(company_name=company_name, domain=company_domain, use_web_search=use_web_search)
            if team_size is not None:
                company.number_of_employees = team_size
            description = fetch_openai_description(company_name=company_name, domain=company_domain, use_web_search=use_web_search)
            if description:
                company.headline = description
            funding = fetch_openai_funding(company_name=company_name, domain=company_domain, use_web_search=use_web_search)
            if funding is not None:
                company.funding = funding
    except Exception as exc:
        # Herstel originele waarden bij fout (nested transaction rollback)
        company.number_of_employees, company.headline, company.funding = originals
        logger.error("Failed to fetch OpenAI data for %s: %s", company_name or company_domain, exc, exc_info=True)


def enrich_company_if_needed(company: Company, domain: Optional[str] = None, use_web_search: bool = False) -> None:
    """Verrijk company-data via OpenAI (team size, beschrijving, funding).
    
    Deze functie wordt aangeroepen tijdens signup en bij competitor toevoeging.
    Het is niet-blockend: als OpenAI faalt, blijft de company bestaan met basisdata.
    
    Args:
        use_web_search: Als True, gebruik web search (langzamer). Standaard False voor performance.
    """
    if not company:
        return
    target_domain = domain or company.domain
    _apply_openai_overrides(company, company.name, target_domain or company.domain, use_web_search=use_web_search)


DEFAULT_LANDSCAPE = (
    "Competitive landscape analysis is being prepared. This section will provide "
    "insights into market positioning, competitive pressures, and strategic "
    "considerations based on available company and competitor data."
)


def _upsert_competitor(comp_data: dict) -> Optional[Company]:
    """Zoek of maak een competitor Company aan vanuit API data.
    
    Gebruikt domain of name matching om te voorkomen dat dezelfde competitor
    meerdere keren wordt aangemaakt. Update alleen velden die nog niet gezet zijn.
    """
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
        db.session.add(competitor)
        db.session.flush()
    
    # Update alleen velden die nog niet gezet zijn (preserve bestaande data)
    field_map = {
        "domain": comp_domain,
        "website": comp_data.get("website"),
        "headline": comp_data.get("description"),
        "industry": comp_data.get("industry")
    }
    for field, val in field_map.items():
        if val and not getattr(competitor, field):
            setattr(competitor, field, val)
    
    return competitor


def _ensure_competitor_link(company: Company, competitor: Company) -> None:
    """Link company aan competitor als deze link nog niet bestaat.
    
    Voorkomt duplicate links en zorgt ervoor dat een company niet zichzelf
    als competitor kan linken.
    """
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


def add_competitor_from_data(company: Company, comp_data: dict, use_web_search: bool = False) -> Optional[Company]:
    """Voeg competitor relatie toe vanuit API payload.
    
    Maakt of vindt de competitor, verrijkt deze met OpenAI data (niet-blockend),
    en linkt deze aan de company. Als enrichment faalt, wordt de competitor
    nog steeds gelinkt (met basisdata).
    
    Args:
        use_web_search: Als True, gebruik web search (langzamer). Standaard False voor performance.
    """
    competitor = _upsert_competitor(comp_data)
    if not competitor:
        return None
    try:
        enrich_company_if_needed(competitor, comp_data.get("domain"), use_web_search=use_web_search)
    except Exception as exc:
        # Log maar blokkeer niet - competitor wordt nog steeds gelinkt
        logger.error("Failed to enrich competitor %s: %s", competitor.name, exc, exc_info=True)
    _ensure_competitor_link(company, competitor)
    return competitor


def refresh_competitors(company: Company) -> None:
    """Vervang competitor links met verse OpenAI resultaten via web search.
    
    BELANGRIJK: Dit VERVANGT alle bestaande competitor links. Oude links worden
    verwijderd voordat nieuwe worden toegevoegd. Dit zorgt ervoor dat de
    competitor lijst altijd up-to-date is met de laatste OpenAI data.
    
    Process:
    - Verwijder eerst alle bestaande competitor-links voor deze company
    - Vraag tot 10 mogelijke rivals op via OpenAI met web search (voor actuele data)
    - Link maximaal 5 nieuwe rivals (met ander domein dan eigen company)
    """
    if not company or not company.domain:
        return
    # Verwijder alle bestaande links - vervang volledig met nieuwe data
    db.session.query(CompanyCompetitor).filter(CompanyCompetitor.company_id == company.id).delete()
    db.session.flush()
    # Gebruik web search voor actuele competitive landscape data (expliciete refresh)
    similar = fetch_openai_similar_companies(company_name=company.name, domain=company.domain, limit=10, use_web_search=True)
    base_domain = (company.domain or "").lower().strip()
    for comp_data in similar[:5]:
        comp_domain = (comp_data.get("domain") or "").lower().strip()
        if not comp_domain or comp_domain == base_domain:
            continue
        add_competitor_from_data(company, comp_data)


def generate_landscape_if_needed(company: Company, use_web_search: bool = False) -> None:
    """Genereer competitive landscape als deze nog niet bestaat.
    
    Gebruikt OpenAI om een samenvatting te maken van de competitive positie.
    Als generatie faalt, wordt DEFAULT_LANDSCAPE gebruikt.
    
    Args:
        use_web_search: Als True, gebruik web search (langzamer). Standaard False voor performance.
    """
    if not company or (company.competitive_landscape or "").strip():
        return
    competitors = get_company_competitors(company)
    if not competitors:
        company.competitive_landscape = DEFAULT_LANDSCAPE
        return
    try:
        with db.session.begin_nested():
            landscape = generate_competitive_landscape(company, competitors, use_web_search=use_web_search)
            company.competitive_landscape = landscape or DEFAULT_LANDSCAPE
    except Exception:
        # Fallback naar default als OpenAI call faalt
        company.competitive_landscape = DEFAULT_LANDSCAPE