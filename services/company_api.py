"""Simple company data API client using CompanyEnrich.

Fetches basic company information from CompanyEnrich API.
Simplified for MVP - uses CompanyEnrich API.

Documentation: https://docs.companyenrich.com/docs/getting-started
API Endpoint: GET https://api.companyenrich.com/companies/enrich?domain=example.com
Similar Companies: POST https://api.companyenrich.com/companies/similar
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional

from app import db
from models import Industry, CompanyIndustry

# Note: load_dotenv() is called in app.py - no need to load here


def fetch_company_info(domain: Optional[str] = None) -> Optional[Dict]:
    """Fetch company data from the CompanyEnrich API.
    
    Args:
        domain: Company domain (e.g., 'example.com')
    
    Returns:
        None if domain is missing or invalid, otherwise dict with normalized company data.
        Dict should be passed to `apply_company_data` and `link_company_industries`.
    """
    if not domain:
        return None
    
    domain = _clean_domain(domain)
    if not domain:
        return None
    
    # Get API key from environment
    api_key = os.getenv("COMPANY_ENRICH_API_KEY")
    
    if not api_key or api_key == "your-api-key-here":
        return {"domain": domain, "name": None, "description": None, "employees": None,
                "industry": None, "country": None, "funding": None, "industries": []}
    
    url = f"https://api.companyenrich.com/companies/enrich?domain={urllib.parse.quote(domain)}"
    
    try:
        request = urllib.request.Request(url)
        request.add_header("Authorization", f"Bearer {api_key}")
        request.add_header("Accept", "application/json")
        
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status == 200:
                response_text = response.read().decode('utf-8')
                data = json.loads(response_text)
                
                employees_num = _parse_employees(data)
                country_str = _parse_country(data)
                financial = data.get("financial", {}) if isinstance(data.get("financial"), dict) else {}
                updated_at_str = data.get("updated_at")
                updated_at = None
                if updated_at_str:
                    try:
                        updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        pass
                
                result = {
                    "name": data.get("name"),
                    "domain": domain,
                    "website": data.get("website"),
                    "description": data.get("description") or data.get("headline"),
                    "employees": employees_num,
                    "industry": data.get("industry") or (data.get("industries")[0] if data.get("industries") else None),
                    "country": country_str,
                    "funding": financial.get("total_funding") or data.get("funding"),
                    "updated_at": updated_at,
                    "industries": data.get("industries", []),
                }
                
                return result
            else:
                return {"domain": domain, "name": None, "description": None, "employees": None,
                        "industry": None, "country": None, "funding": None, "industries": []}
                
    except urllib.error.HTTPError:
        return {"domain": domain, "name": None, "description": None, "employees": None,
                "industry": None, "country": None, "funding": None, "industries": []}
    except Exception:
        return {"domain": domain, "name": None, "description": None, "employees": None,
                "industry": None, "country": None, "funding": None, "industries": []}


def _clean_domain(domain: str) -> str:
    """Clean and normalize domain string."""
    if not domain:
        return ""
    domain = domain.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def fetch_similar_companies(domain: Optional[str] = None, limit: int = 10) -> List[Dict]:
    """Fetch similar companies (competitors) from CompanyEnrich API.
    
    Uses POST /companies/similar endpoint to find competitors.
    Costs: 5 credits per company returned.
    
    Args:
        domain: Company domain (e.g., 'example.com')
        limit: Maximum number of competitors to return (1-100, default 10)
        
    Returns:
        List of company dictionaries or empty list if not found/API fails
    """
    if not domain:
        return []

    api_key = os.getenv("COMPANY_ENRICH_API_KEY")
    if not api_key or api_key == "your-api-key-here":
        return []
    
    limit = max(1, min(100, limit))
    url = "https://api.companyenrich.com/companies/similar"
    
    try:
        domain_clean = _clean_domain(domain)
        body = {
            "domains": [domain_clean],
            "pageSize": limit,
            "exclude": {
                "domains": [domain_clean]
            }
        }
        
        request = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'))
        request.add_header("Authorization", f"Bearer {api_key}")
        request.add_header("Accept", "application/json")
        request.add_header("Content-Type", "application/json")
        
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status == 200:
                response_text = response.read().decode('utf-8')
                data = json.loads(response_text)
                
                companies = []
                if isinstance(data, dict):
                    companies = data.get("items", [])
                elif isinstance(data, list):
                    companies = data
                
                result = []
                for company_data in companies:
                    competitor_domain = company_data.get("domain")
                    if not competitor_domain:
                        continue
                    
                    competitor_domain_clean = _clean_domain(competitor_domain)
                    if competitor_domain_clean == domain_clean:
                        continue
                    
                    result.append({
                        "name": company_data.get("name") or "Unknown",
                        "domain": competitor_domain,
                        "website": company_data.get("website"),
                        "description": company_data.get("description") or company_data.get("headline"),
                        "industry": company_data.get("industry"),
                        "employees": company_data.get("employees") or company_data.get("employee_count"),
                        "country": company_data.get("country") or company_data.get("headquarters_country"),
                    })
                
                return result
            else:
                return []
                
    except urllib.error.HTTPError:
        return []
    except Exception:
        return []


def apply_company_data(company, api_data: Dict) -> None:
    """Apply API data to company object.
    
    Only updates fields that are empty and API has data for.
    This ensures form data takes precedence.
    
    Edge Cases:
    - Domain is always updated if API provides it (ensures consistency)
    - Other fields only update if empty (preserves existing data)
    - updated_at is always updated if available (tracks last API fetch)
    - Industries are handled separately in routes/auth.py
    
    Args:
        company: Company model instance
        api_data: Dictionary with company data from API
    """
    if not company or not api_data:
        return
    
    if api_data.get("domain"):
        company.domain = api_data["domain"]
    
    if not company.website and api_data.get("website"):
        company.website = api_data["website"]
    
    if not company.headline and api_data.get("description"):
        company.headline = api_data["description"]
    
    if not company.number_of_employees and api_data.get("employees"):
        try:
            company.number_of_employees = int(api_data["employees"])
        except (ValueError, TypeError):
            pass
    
    if not company.industry and api_data.get("industry"):
        company.industry = api_data["industry"]
    
    if not company.country and api_data.get("country"):
        company.country = api_data["country"]
    
    if not company.funding and api_data.get("funding"):
        try:
            company.funding = int(api_data["funding"])
        except (ValueError, TypeError):
            pass
    
    if api_data.get("updated_at"):
        company.updated_at = api_data["updated_at"]
    


def needs_api_fetch(company, domain: Optional[str] = None) -> bool:
    """Check if company needs API data fetch.
    
    Args:
        company: Company model instance
        domain: Optional domain to check against
        
    Returns:
        True if API fetch is needed, False otherwise
    """
    if not company or not domain:
        return False
    
    return bool(
        not company.updated_at or
        company.domain != domain or
        not company.headline
    )


def _parse_employees(data: Dict) -> Optional[int]:
    """Parse employee count from API data."""
    employees_value = data.get("employees") or data.get("employee_count")
    if not employees_value:
        return None

    if isinstance(employees_value, (int, float)):
        return int(employees_value)
    elif isinstance(employees_value, str):
        numbers = re.findall(r"\d+", employees_value.replace(",", ""))
        if numbers:
            num = int(numbers[0])
            if "k" in employees_value.lower():
                return num * 1000
            return num

    return None


def _parse_country(data: Dict) -> Optional[str]:
    """Parse country from API data."""
    country_value = data.get("country") or data.get("headquarters_country")
    if not country_value:
        location = data.get("location", {})
        if isinstance(location, dict):
            country_value = location.get("country")
    
    if isinstance(country_value, dict):
        return country_value.get("name") or country_value.get("code")
    elif isinstance(country_value, str):
        return country_value
    
    return None


def link_company_industries(company, industries_list: List[str]) -> None:
    """Link company to industries from API data.
    
    Args:
        company: Company model instance
        industries_list: List of industry names from API
    """
    if not company or not industries_list:
        return

    for industry_name in industries_list:
        parsed_name = industry_name.split("/")[-1].strip() if "/" in industry_name else industry_name.strip()
        industry = db.session.query(Industry).filter(Industry.name == parsed_name).first()
        if not industry:
            industry = Industry(name=parsed_name)
            db.session.add(industry)
            db.session.flush()

        existing_link = db.session.query(CompanyIndustry).filter(
            CompanyIndustry.company_id == company.id,
            CompanyIndustry.industry_id == industry.id
        ).first()
        if not existing_link:
            link = CompanyIndustry(company_id=company.id, industry_id=industry.id)
            db.session.add(link)
