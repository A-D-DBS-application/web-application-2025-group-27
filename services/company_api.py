import json, os, re, urllib.error, urllib.parse, urllib.request
from datetime import datetime
from typing import Dict, List, Optional
from app import db
from models import Industry, CompanyIndustry

EMPTY_RESPONSE = {"name": None, "description": None, "employees": None, "industry": None, "country": None, "funding": None, "industries": []}


def _clean_domain(domain: str) -> str:
    if not domain: return ""
    d = domain.lower().strip()
    return d[4:] if d.startswith("www.") else d


def _parse_employees(data: Dict) -> Optional[int]:
    val = data.get("employees") or data.get("employee_count")
    if not val: return None
    if isinstance(val, (int, float)): return int(val)
    if isinstance(val, str):
        nums = re.findall(r"\d+", val.replace(",", ""))
        if nums:
            n = int(nums[0])
            return n * 1000 if "k" in val.lower() else n
    return None


def _parse_country(data: Dict) -> Optional[str]:
    val = data.get("country") or data.get("headquarters_country") or (data.get("location", {}) or {}).get("country")
    if isinstance(val, dict): return val.get("name") or val.get("code")
    return val if isinstance(val, str) else None


def fetch_company_info(domain: Optional[str] = None) -> Optional[Dict]:
    if not domain: return None
    domain = _clean_domain(domain)
    if not domain: return None
    
    api_key = os.getenv("COMPANY_ENRICH_API_KEY")
    if not api_key or api_key == "your-api-key-here":
        return {"domain": domain, **EMPTY_RESPONSE}
    
    url = f"https://api.companyenrich.com/companies/enrich?domain={urllib.parse.quote(domain)}"
    try:
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Accept", "application/json")
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return {"domain": domain, **EMPTY_RESPONSE}
            
            data = json.loads(resp.read().decode('utf-8'))
            financial = data.get("financial", {}) if isinstance(data.get("financial"), dict) else {}
            updated_at = None
            if data.get("updated_at"):
                try: updated_at = datetime.fromisoformat(data["updated_at"].replace('Z', '+00:00'))
                except (ValueError, AttributeError): pass
            
            return {
                "name": data.get("name"),
                "domain": domain,
                "website": data.get("website"),
                "description": data.get("description") or data.get("headline"),
                "employees": _parse_employees(data),
                "industry": data.get("industry") or (data.get("industries")[0] if data.get("industries") else None),
                "country": _parse_country(data),
                "funding": financial.get("total_funding") or data.get("funding"),
                "updated_at": updated_at,
                "industries": data.get("industries", []),
            }
    except Exception:
        return {"domain": domain, **EMPTY_RESPONSE}


def fetch_similar_companies(domain: Optional[str] = None, limit: int = 10) -> List[Dict]:
    if not domain: return []
    api_key = os.getenv("COMPANY_ENRICH_API_KEY")
    if not api_key or api_key == "your-api-key-here": return []
    
    domain_clean = _clean_domain(domain)
    body = {"domains": [domain_clean], "pageSize": max(1, min(100, limit)), "exclude": {"domains": [domain_clean]}}
    
    try:
        req = urllib.request.Request("https://api.companyenrich.com/companies/similar", data=json.dumps(body).encode('utf-8'))
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Accept", "application/json")
        req.add_header("Content-Type", "application/json")
        
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200: return []
            data = json.loads(resp.read().decode('utf-8'))
            companies = data.get("items", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            
            result = []
            for c in companies:
                comp_domain = c.get("domain")
                if not comp_domain or _clean_domain(comp_domain) == domain_clean: continue
                result.append({
                    "name": c.get("name") or "Unknown",
                    "domain": comp_domain,
                    "website": c.get("website"),
                    "description": c.get("description") or c.get("headline"),
                    "industry": c.get("industry"),
                    "employees": c.get("employees") or c.get("employee_count"),
                    "country": c.get("country") or c.get("headquarters_country"),
                })
            return result
    except Exception:
        return []


def apply_company_data(company, api_data: Dict) -> None:
    if not company or not api_data: return
    if api_data.get("domain"): company.domain = api_data["domain"]
    if not company.website and api_data.get("website"): company.website = api_data["website"]
    if not company.headline and api_data.get("description"): company.headline = api_data["description"]
    if not company.number_of_employees and api_data.get("employees"):
        try: company.number_of_employees = int(api_data["employees"])
        except (ValueError, TypeError): pass
    if not company.industry and api_data.get("industry"): company.industry = api_data["industry"]
    if not company.country and api_data.get("country"): company.country = api_data["country"]
    if not company.funding and api_data.get("funding"):
        try: company.funding = int(api_data["funding"])
        except (ValueError, TypeError): pass
    if api_data.get("updated_at"): company.updated_at = api_data["updated_at"]


def needs_api_fetch(company, domain: Optional[str] = None) -> bool:
    if not company or not domain: return False
    return not company.updated_at or company.domain != domain or not company.headline


def link_company_industries(company, industries_list: List[str]) -> None:
    if not company or not industries_list: return
    for name in industries_list:
        parsed = name.split("/")[-1].strip() if "/" in name else name.strip()
        industry = db.session.query(Industry).filter(Industry.name == parsed).first()
        if not industry:
            industry = Industry(name=parsed)
            db.session.add(industry)
            db.session.flush()
        if not db.session.query(CompanyIndustry).filter_by(company_id=company.id, industry_id=industry.id).first():
            db.session.add(CompanyIndustry(company_id=company.id, industry_id=industry.id))
