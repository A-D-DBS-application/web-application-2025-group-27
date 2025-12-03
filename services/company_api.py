import json, os, re, urllib.error, urllib.parse, urllib.request
from datetime import datetime
from typing import Dict, List, Optional
from app import db
from models import Industry, CompanyIndustry, Company

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

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
    """Fetch company information using Company Enrich API for basic fields ONLY. OpenAI is used for team size, description, and funding."""
    if not domain: return None
    domain = _clean_domain(domain)
    if not domain: return None
    
    # First, try to get basic info from Company Enrich API (name, website, industry, country, industries)
    # NOTE: We do NOT use Company Enrich for description, employees, or funding - those come from OpenAI
    api_key = os.getenv("COMPANY_ENRICH_API_KEY")
    basic_data = {"domain": domain}
    
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
    company_name = basic_data.get("name")
    
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
    if not OpenAI:
        import logging
        logging.warning("OpenAI library not available")
        return []
    
    if not company_name and not domain:
        import logging
        logging.warning("No company name or domain provided for competitor lookup")
        return []
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-api-key-here" or api_key.strip() == "":
        import logging
        logging.warning("OPENAI_API_KEY not set or invalid")
        return []
    
    try:
        client = OpenAI(api_key=api_key)
        
        search_query = f"{company_name or domain}"
        if domain and company_name:
            search_query += f" ({domain})"
        
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

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides accurate competitor information. You must always respond with valid JSON only, no additional text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent results
            max_tokens=2000,
            response_format={"type": "json_object"}  # Force JSON output
        )
        
        if not response or not response.choices or not response.choices[0].message:
            import logging
            logging.warning("Empty response from OpenAI")
            return []
        
        response_text = response.choices[0].message.content.strip()
        
        if not response_text:
            import logging
            logging.warning("Empty response text from OpenAI")
            return []
        
        # Try to parse JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            import logging
            logging.error(f"Failed to parse JSON response from OpenAI. Response: {response_text[:500]}, Error: {e}")
            return []
        
        competitors = data.get("competitors", [])
        if not isinstance(competitors, list):
            import logging
            logging.warning("Competitors data is not a list")
            return []
        
        # Clean and format the results
        result = []
        domain_clean = _clean_domain(domain) if domain else None
        
        for comp in competitors:
            if not isinstance(comp, dict):
                continue
            
            comp_domain = comp.get("domain")
            if not comp_domain:
                continue
            
            # Clean domain
            comp_domain = _clean_domain(comp_domain)
            
            # Skip if it's the same company
            if domain_clean and comp_domain == domain_clean:
                continue
            
            # Extract website from domain if not provided
            website = comp.get("website")
            if not website and comp_domain:
                website = f"https://{comp_domain}"
            
            result.append({
                "name": comp.get("name") or "Unknown",
                "domain": comp_domain,
                "website": website,
                "industry": comp.get("industry"),
                "country": comp.get("country"),
                # Note: employees and description will be fetched later via OpenAI
                "employees": None,
                "description": None,
            })
        
        import logging
        logging.info(f"Successfully fetched {len(result)} competitors from OpenAI for {search_query}")
        return result[:limit]  # Limit results
        
    except Exception as e:
        import logging
        logging.error(f"Error fetching OpenAI competitors for {company_name or domain}: {e}", exc_info=True)
        return []


def fetch_similar_companies(domain: Optional[str] = None, limit: int = 10) -> List[Dict]:
    """DEPRECATED: Use fetch_openai_similar_companies() instead.
    
    This function is kept for backward compatibility but should not be used.
    It uses Company Enrich API which is less accurate than OpenAI.
    """
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
            industry = Industry(name=parsed)
            db.session.add(industry)
            db.session.flush()
        if not db.session.query(CompanyIndustry).filter_by(company_id=company.id, industry_id=industry.id).first():
            db.session.add(CompanyIndustry(company_id=company.id, industry_id=industry.id))


def fetch_openai_funding(company_name: Optional[str] = None, domain: Optional[str] = None) -> Optional[int]:
    """Fetch company funding information using OpenAI API.
    
    For publicly traded companies, returns market capitalization instead of funding.
    
    Args:
        company_name: Company name (e.g., 'Nike')
        domain: Company domain (e.g., 'nike.com')
        
    Returns:
        Funding amount or market cap as integer (in base currency units), or None if not found/fails
    """
    if not OpenAI:
        import logging
        logging.warning("OpenAI library not available")
        return None
    
    if not company_name and not domain:
        import logging
        logging.warning("No company name or domain provided for funding lookup")
        return None
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-api-key-here" or api_key.strip() == "":
        import logging
        logging.warning("OPENAI_API_KEY not set or invalid")
        return None
    
    try:
        client = OpenAI(api_key=api_key)
        
        search_query = f"{company_name or domain}"
        if domain and company_name:
            search_query += f" ({domain})"
        
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

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides accurate company funding and market capitalization information. You must always respond with valid JSON only, no additional text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Lower temperature for more consistent results
            max_tokens=200,
            response_format={"type": "json_object"}  # Force JSON output
        )
        
        if not response or not response.choices or not response.choices[0].message:
            import logging
            logging.warning("Empty response from OpenAI")
            return None
        
        response_text = response.choices[0].message.content.strip()
        
        if not response_text:
            import logging
            logging.warning("Empty response text from OpenAI")
            return None
        
        # Try to parse JSON from response (with response_format, it should be clean JSON)
        # But handle cases where markdown code blocks might still be present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            import logging
            logging.error(f"Failed to parse JSON response from OpenAI. Response: {response_text[:500]}, Error: {e}")
            return None
        
        funding_value = data.get("funding")
        
        if funding_value is None:
            import logging
            logging.info(f"OpenAI returned null funding for {search_query}")
            return None
        
        # Convert to integer
        if isinstance(funding_value, (int, float)):
            result = int(funding_value)
            import logging
            logging.info(f"Successfully fetched funding/market cap for {search_query}: {result} (public: {data.get('is_public', False)})")
            return result
        elif isinstance(funding_value, str):
            # Try to extract number from string
            if funding_value.lower() in ["unknown", "n/a", "null", "none", ""]:
                return None
            # Handle strings like "50M", "1.5B", etc.
            funding_lower = funding_value.lower().strip()
            multiplier = 1
            if funding_lower.endswith('b'):
                multiplier = 1000000000
                funding_lower = funding_lower[:-1]
            elif funding_lower.endswith('m'):
                multiplier = 1000000
                funding_lower = funding_lower[:-1]
            elif funding_lower.endswith('k'):
                multiplier = 1000
                funding_lower = funding_lower[:-1]
            
            # Remove currency symbols and extract number
            numbers = re.findall(r'\d+\.?\d*', funding_lower.replace(',', ''))
            if numbers:
                result = int(float(numbers[0]) * multiplier)
                import logging
                logging.info(f"Successfully parsed funding string for {search_query}: {result}")
                return result
        
        import logging
        logging.warning(f"Could not parse funding value: {funding_value} for {search_query}")
        return None
        
    except Exception as e:
        import logging
        logging.error(f"Error fetching OpenAI funding for {company_name or domain}: {e}", exc_info=True)
        return None


def fetch_openai_team_size(company_name: Optional[str] = None, domain: Optional[str] = None) -> Optional[int]:
    """Fetch company team size (number of employees) using OpenAI API.
    
    Args:
        company_name: Company name (e.g., 'Nike')
        domain: Company domain (e.g., 'nike.com')
        
    Returns:
        Number of employees as integer, or None if not found/fails
    """
    if not OpenAI:
        import logging
        logging.warning("OpenAI library not available")
        return None
    
    if not company_name and not domain:
        import logging
        logging.warning("No company name or domain provided for team size lookup")
        return None
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-api-key-here" or api_key.strip() == "":
        import logging
        logging.warning("OPENAI_API_KEY not set or invalid")
        return None
    
    try:
        client = OpenAI(api_key=api_key)
        
        search_query = f"{company_name or domain}"
        if domain and company_name:
            search_query += f" ({domain})"
        
        prompt = f"""Please provide the current number of employees (team size) for the company "{search_query}".

You must respond with valid JSON in this exact format:
{{
    "employees": 10000
}}

Where employees is the total number of employees as an integer. Use null if the information is not available."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides accurate company employee count information. You must always respond with valid JSON only, no additional text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Lower temperature for more consistent results
            max_tokens=200,
            response_format={"type": "json_object"}  # Force JSON output
        )
        
        if not response or not response.choices or not response.choices[0].message:
            import logging
            logging.warning("Empty response from OpenAI")
            return None
        
        response_text = response.choices[0].message.content.strip()
        
        if not response_text:
            import logging
            logging.warning("Empty response text from OpenAI")
            return None
        
        # Try to parse JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            import logging
            logging.error(f"Failed to parse JSON response from OpenAI. Response: {response_text[:500]}, Error: {e}")
            return None
        
        employees_value = data.get("employees")
        
        if employees_value is None:
            import logging
            logging.info(f"OpenAI returned null employees for {search_query}")
            return None
        
        # Convert to integer
        if isinstance(employees_value, (int, float)):
            result = int(employees_value)
            import logging
            logging.info(f"Successfully fetched team size for {search_query}: {result}")
            return result
        elif isinstance(employees_value, str):
            # Try to extract number from string
            if employees_value.lower() in ["unknown", "n/a", "null", "none", ""]:
                return None
            # Handle strings like "10k", "1.5M", etc.
            employees_lower = employees_value.lower().strip()
            multiplier = 1
            if employees_lower.endswith('m'):
                multiplier = 1000000
                employees_lower = employees_lower[:-1]
            elif employees_lower.endswith('k'):
                multiplier = 1000
                employees_lower = employees_lower[:-1]
            
            # Remove commas and extract number
            numbers = re.findall(r'\d+\.?\d*', employees_lower.replace(',', ''))
            if numbers:
                result = int(float(numbers[0]) * multiplier)
                import logging
                logging.info(f"Successfully parsed employees string for {search_query}: {result}")
                return result
        
        import logging
        logging.warning(f"Could not parse employees value: {employees_value} for {search_query}")
        return None
        
    except Exception as e:
        import logging
        logging.error(f"Error fetching OpenAI team size for {company_name or domain}: {e}", exc_info=True)
        return None


def fetch_openai_description(company_name: Optional[str] = None, domain: Optional[str] = None) -> Optional[str]:
    """Fetch company description using OpenAI API.
    
    Args:
        company_name: Company name (e.g., 'Nike')
        domain: Company domain (e.g., 'nike.com')
        
    Returns:
        Company description as string, or None if not found/fails
    """
    if not OpenAI:
        import logging
        logging.warning("OpenAI library not available")
        return None
    
    if not company_name and not domain:
        import logging
        logging.warning("No company name or domain provided for description lookup")
        return None
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-api-key-here" or api_key.strip() == "":
        import logging
        logging.warning("OPENAI_API_KEY not set or invalid")
        return None
    
    try:
        client = OpenAI(api_key=api_key)
        
        search_query = f"{company_name or domain}"
        if domain and company_name:
            search_query += f" ({domain})"
        
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

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides accurate company descriptions. You must always respond with valid JSON only, no additional text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Slightly higher for more natural descriptions
            max_tokens=300,
            response_format={"type": "json_object"}  # Force JSON output
        )
        
        if not response or not response.choices or not response.choices[0].message:
            import logging
            logging.warning("Empty response from OpenAI")
            return None
        
        response_text = response.choices[0].message.content.strip()
        
        if not response_text:
            import logging
            logging.warning("Empty response text from OpenAI")
            return None
        
        # Try to parse JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            import logging
            logging.error(f"Failed to parse JSON response from OpenAI. Response: {response_text[:500]}, Error: {e}")
            return None
        
        description = data.get("description")
        
        if not description or description.lower() in ["null", "none", "unknown", "n/a", ""]:
            import logging
            logging.info(f"OpenAI returned null/empty description for {search_query}")
            return None
        
        import logging
        logging.info(f"Successfully fetched description for {search_query}")
        return description.strip()
        
    except Exception as e:
        import logging
        logging.error(f"Error fetching OpenAI description for {company_name or domain}: {e}", exc_info=True)
        return None
