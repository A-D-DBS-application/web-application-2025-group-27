import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, cast

from app import db
from models import Company, CompanyIndustry, Industry
from services.openai_helpers import chat_json

EMPTY_RESPONSE = {"name": None, "description": None, "employees": None, "industry": None, "country": None, "funding": None, "industries": []}


def _build_search_query(company_name: Optional[str], domain: Optional[str], context: str) -> Optional[str]:
    """Combine company name and domain for prompts."""
    if not company_name and not domain:
        return None
    base = company_name or domain
    query = cast(str, base)
    if domain and company_name:
        query += f" ({domain})"
    return query


def _clean_domain(domain: str) -> str:
    if not domain: return ""
    d = domain.lower().strip()
    return d[4:] if d.startswith("www.") else d


def _parse_country(data: Dict) -> Optional[str]:
    val = data.get("country") or data.get("headquarters_country") or (data.get("location", {}) or {}).get("country")
    if isinstance(val, dict): return val.get("name") or val.get("code")
    return val if isinstance(val, str) else None


def _parse_numeric_value(value, suffix_multipliers: Dict[str, int]) -> Optional[int]:
    """Parse numeric strings like '10k' or '2.5B' into integers."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.lower().strip()
        if cleaned in {"unknown", "n/a", "null", "none", ""}:
            return None
        multiplier = 1
        for suffix, factor in suffix_multipliers.items():
            if cleaned.endswith(suffix):
                multiplier = factor
                cleaned = cleaned[:-len(suffix)]
                break
        numbers = re.findall(r"\d+\.?\d*", cleaned.replace(",", ""))
        if numbers:
            return int(float(numbers[0]) * multiplier)
    return None


def _fetch_numeric_value(
    *,
    search_query: str,
    prompt: str,
    system_prompt: str,
    field_name: str,
    suffixes: Dict[str, int],
    log_label: str,
    temperature: float = 0.1,
    max_tokens: int = 200,
) -> Optional[int]:
    data = chat_json(
        system_prompt=system_prompt,
        user_prompt=prompt,
        model="gpt-4o",
        temperature=temperature,
        max_tokens=max_tokens,
        context=f"{log_label} for {search_query}",
    )
    if not data:
        return None
    value = data.get(field_name)
    parsed = _parse_numeric_value(value, suffixes)
    if parsed is None:
        return None
    return parsed


def fetch_company_info(domain: Optional[str] = None) -> Optional[Dict]:
    """Fetch company information using Company Enrich API for basic fields ONLY. OpenAI is used for team size, description, and funding."""
    if not domain: return None
    domain = _clean_domain(domain)
    if not domain: return None
    
    # First, try to get basic info from Company Enrich API (name, website, industry, country, industries)
    # NOTE: We do NOT use Company Enrich for description, employees, or funding - those come from OpenAI
    api_key = os.getenv("COMPANY_ENRICH_API_KEY")
    basic_data: Dict[str, object] = {"domain": domain}
    
    if api_key and api_key != "your-api-key-here":
        url = f"https://api.companyenrich.com/companies/enrich?domain={urllib.parse.quote(domain)}"
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {api_key}")
            req.add_header("Accept", "application/json")
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    updated_at = None
                    if data.get("updated_at"):
                        try: updated_at = datetime.fromisoformat(data["updated_at"].replace('Z', '+00:00'))
                        except (ValueError, AttributeError): pass
                    
                    # ONLY extract basic fields - NOT description, employees, or funding
                    basic_data.update({
                        "name": data.get("name"),
                        "website": data.get("website"),
                        "industry": data.get("industry") or (data.get("industries")[0] if data.get("industries") else None),
                        "country": _parse_country(data),
                        "updated_at": updated_at,
                        "industries": data.get("industries", []),
                    })
        except Exception:
            pass  # Continue with OpenAI calls even if Company Enrich fails
    
    # ALWAYS use OpenAI for team size, description, and funding (never use Company Enrich for these)
    company_name = cast(Optional[str], basic_data.get("name"))
    
    # Fetch team size from OpenAI (replaces Company Enrich)
    employees = fetch_openai_team_size(company_name=company_name, domain=domain)
    
    # Fetch description from OpenAI (replaces Company Enrich)
    description = fetch_openai_description(company_name=company_name, domain=domain)
    
    # Fetch funding/market cap from OpenAI (replaces Company Enrich)
    # For public companies, this returns market capitalization
    funding = fetch_openai_funding(company_name=company_name, domain=domain)
    
    # Combine all data - OpenAI fields take precedence
    result = {
        **basic_data,
        "description": description,  # From OpenAI only
        "employees": employees,      # From OpenAI only
        "funding": funding,           # From OpenAI only (market cap for public companies)
    }
    
    # Fill in defaults for missing fields
    for key, default_value in EMPTY_RESPONSE.items():
        if key not in result or result[key] is None:
            result[key] = default_value
    
    return result


def fetch_openai_similar_companies(company_name: Optional[str] = None, domain: Optional[str] = None, limit: int = 10) -> List[Dict]:
    """Fetch similar companies/competitors using OpenAI API.
    
    This replaces Company Enrich API for more accurate competitor identification.
    
    Args:
        company_name: Company name (e.g., 'Apple')
        domain: Company domain (e.g., 'apple.com')
        limit: Maximum number of competitors to return
        
    Returns:
        List of competitor dictionaries with name, domain, website, industry, country
    """
    search_query = _build_search_query(company_name, domain, "competitor")
    if not search_query:
        return []
    
    prompt = f"""Please identify the MAIN DIRECT competitors of the company "{search_query}".

Focus on the PRIMARY competitors - major companies that directly compete in the same core markets and product categories. These should be well-known, established companies of similar or larger scale that compete head-to-head.

IMPORTANT:
- Prioritize major, well-known competitors (Fortune 500/Global 500 companies when applicable)
- Focus on companies that compete in the SAME core product categories
- Exclude subsidiaries, resellers, distributors, or smaller regional players
- Exclude companies that are primarily suppliers, partners, or operate in adjacent markets
- For tech companies: focus on other major tech companies competing in the same product segments
- For consumer brands: focus on other major consumer brands in the same category

You must respond with valid JSON in this exact format:
{{
    "competitors": [
        {{
            "name": "Competitor Company Name",
            "domain": "competitor.com",
            "website": "https://competitor.com",
            "industry": "Technology",
            "country": "United States"
        }}
    ]
}}

Requirements:
- Provide {limit} MAIN DIRECT competitors (major companies only)
- Include the company's main domain (e.g., "apple.com" not "www.apple.com")
- Include the full website URL with https://
- Include the primary industry
- Include the country where the company is headquartered
- Only include major, well-established competitors of similar scale
- Do NOT include the company itself
- Do NOT include subsidiaries, resellers, or small regional players
- Use null for any field if information is not available"""

    data = chat_json(
        system_prompt="You are a helpful assistant that provides accurate competitor information. You must always respond with valid JSON only, no additional text.",
        user_prompt=prompt,
        model="gpt-4o",
        temperature=0.3,
        max_tokens=2000,
        context=f"competitors for {search_query}",
    )
    if not data:
        return []
    
    competitors = data.get("competitors", [])
    if not isinstance(competitors, list):
        return []
    
    result = []
    domain_clean = _clean_domain(domain) if domain else None
    
    for comp in competitors:
        if not isinstance(comp, dict):
            continue
        
        comp_domain = comp.get("domain")
        if not comp_domain:
            continue
        
        comp_domain = _clean_domain(comp_domain)
        if domain_clean and comp_domain == domain_clean:
            continue
        
        website = comp.get("website") or (f"https://{comp_domain}" if comp_domain else None)
        
        result.append({
            "name": comp.get("name") or "Unknown",
            "domain": comp_domain,
            "website": website,
            "industry": comp.get("industry"),
            "country": comp.get("country"),
            "employees": None,
            "description": None,
        })
    
    return result[:limit]


def apply_company_data(company, api_data: Dict) -> None:
    """Apply company data from API response using SQLAlchemy ORM.
    
    Note: OpenAI fields (description, employees, funding) are ALWAYS applied,
    even if they already exist, to ensure we use OpenAI data instead of Company Enrich.
    """
    if not company or not api_data:
        return
    
    # Use SQLAlchemy ORM to update company fields directly
    # Update in-memory object (SQLAlchemy tracks changes automatically)
    if api_data.get("domain"):
        company.domain = api_data["domain"]
    if not company.website and api_data.get("website"):
        company.website = api_data["website"]
    
    # ALWAYS apply OpenAI fields (description, employees, funding) - these come from OpenAI, not Company Enrich
    # We always update these to ensure OpenAI data takes precedence
    if api_data.get("description"):
        company.headline = api_data["description"]
    if api_data.get("employees") is not None:
        try:
            company.number_of_employees = int(api_data["employees"])
        except (ValueError, TypeError):
            pass
    if api_data.get("funding") is not None:
        try:
            company.funding = int(api_data["funding"])
        except (ValueError, TypeError):
            pass
    
    # Apply basic fields (only if not already set)
    if not company.industry and api_data.get("industry"):
        company.industry = api_data["industry"]
    if not company.country and api_data.get("country"):
        company.country = api_data["country"]
    if api_data.get("updated_at"):
        company.updated_at = api_data["updated_at"]
    
    # SQLAlchemy automatically tracks changes to the object, no need for explicit update query


def needs_api_fetch(company, domain: Optional[str] = None) -> bool:
    if not company or not domain: return False
    return not company.updated_at or company.domain != domain or not company.headline


def link_company_industries(company, industries_list: List[str]) -> None:
    if not company or not industries_list: return
    for name in industries_list:
        parsed = name.split("/")[-1].strip() if "/" in name else name.strip()
        industry = db.session.query(Industry).filter(Industry.name == parsed).first()
        if not industry:
            industry = Industry(name=parsed)  # type: ignore[arg-type]
            db.session.add(industry)
            db.session.flush()
        if not db.session.query(CompanyIndustry).filter_by(company_id=company.id, industry_id=industry.id).first():
            db.session.add(CompanyIndustry(company_id=company.id, industry_id=industry.id))  # type: ignore[arg-type]


def fetch_openai_funding(company_name: Optional[str] = None, domain: Optional[str] = None) -> Optional[int]:
    """Fetch company funding information using OpenAI API.
    
    For publicly traded companies, returns market capitalization instead of funding.
    
    Args:
        company_name: Company name (e.g., 'Nike')
        domain: Company domain (e.g., 'nike.com')
        
    Returns:
        Funding amount or market cap as integer (in base currency units), or None if not found/fails
    """
    search_query = _build_search_query(company_name, domain, "funding")
    if not search_query:
        return None
    
    prompt = f"""Please provide the funding or market capitalization for the company "{search_query}".

IMPORTANT:
- For PRIVATELY HELD companies: Provide the total funding amount raised across all funding rounds (seed, Series A, B, C, etc.).
- For PUBLICLY TRADED (listed) companies: Provide the CURRENT MARKET CAPITALIZATION instead of funding. Market cap is more relevant for public companies.

You must respond with valid JSON in this exact format:
{{
    "funding": 50000000,
    "is_public": false
}}

Where:
- funding: The total funding amount (for private companies) OR current market capitalization (for public/listed companies) in base currency units (e.g., USD)
- is_public: Boolean indicating if the company is publicly traded/listed
- Use null for funding if information is not available

For listed companies, always use market capitalization as it is more accurate and relevant than funding."""

    return _fetch_numeric_value(
        search_query=search_query,
        prompt=prompt,
        system_prompt="You are a helpful assistant that provides accurate company funding and market capitalization information. You must always respond with valid JSON only, no additional text.",
        field_name="funding",
        suffixes={"b": 1_000_000_000, "m": 1_000_000, "k": 1_000},
        log_label="funding/market cap",
        temperature=0.1,
        max_tokens=200,
    )


def fetch_openai_team_size(company_name: Optional[str] = None, domain: Optional[str] = None) -> Optional[int]:
    """Fetch company team size (number of employees) using OpenAI API.
    
    Args:
        company_name: Company name (e.g., 'Nike')
        domain: Company domain (e.g., 'nike.com')
        
    Returns:
        Number of employees as integer, or None if not found/fails
    """
    search_query = _build_search_query(company_name, domain, "team size")
    if not search_query:
        return None
    
    prompt = f"""Please provide the current number of employees (team size) for the company "{search_query}".

You must respond with valid JSON in this exact format:
{{
    "employees": 10000
}}

Where employees is the total number of employees as an integer. Use null if the information is not available."""

    return _fetch_numeric_value(
        search_query=search_query,
        prompt=prompt,
        system_prompt="You are a helpful assistant that provides accurate company employee count information. You must always respond with valid JSON only, no additional text.",
        field_name="employees",
        suffixes={"m": 1_000_000, "k": 1_000},
        log_label="team size",
        temperature=0.1,
        max_tokens=200,
    )


def fetch_openai_description(company_name: Optional[str] = None, domain: Optional[str] = None) -> Optional[str]:
    """Fetch company description using OpenAI API.
    
    Args:
        company_name: Company name (e.g., 'Nike')
        domain: Company domain (e.g., 'nike.com')
        
    Returns:
        Company description as string, or None if not found/fails
    """
    search_query = _build_search_query(company_name, domain, "description")
    if not search_query:
        return None
    
    prompt = f"""Please provide a comprehensive description of the company "{search_query}".

The description should be informative and professional, covering:
- What the company does
- Its main products or services
- Its market focus
- Key differentiators or notable aspects

Keep it concise but informative (2-4 sentences). Write in a professional tone suitable for a company profile page.

You must respond with valid JSON in this exact format:
{{
    "description": "Company description text here..."
}}

Use null for description if information is not available."""

    data = chat_json(
        system_prompt="You are a helpful assistant that provides accurate company descriptions. You must always respond with valid JSON only, no additional text.",
        user_prompt=prompt,
        model="gpt-4o",
        temperature=0.3,
        max_tokens=300,
        context=f"description for {search_query}",
    )
    if not data:
        return None
    
    description = data.get("description")
    if not description or description.lower() in {"null", "none", "unknown", "n/a", ""}:
        return None
    
    return description.strip()
