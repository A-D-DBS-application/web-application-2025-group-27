"""Service-functies voor externe bedrijfsdata.

Deze module:
- gebruikt OpenAI om teamgrootte, beschrijving, funding en competitors op te halen
- biedt eenvoudige helpers die door de rest van de app worden gebruikt
"""

import re
from typing import Dict, List, Optional, cast

from services.openai_helpers import chat_json, responses_json_with_sources


def _build_search_query(company_name: Optional[str], domain: Optional[str]) -> Optional[str]:
    """Combine company name and domain for prompts."""
    if not company_name and not domain:
        return None
    query = cast(str, company_name or domain)
    return f"{query} ({domain})" if domain and company_name else query


def _clean_domain(domain: str) -> str:
    if not domain:
        return ""
    d = domain.lower().strip()
    return d[4:] if d.startswith("www.") else d


def _parse_numeric_value(value, suffix_multipliers: Dict[str, int]) -> Optional[int]:
    """Parse numerieke strings zoals '10k' of '2.5B' naar integers.
    
    Ondersteunt suffix multipliers (k=1000, m=1M, b=1B) en handhaaft
    verschillende formaten (decimaal, met komma's). Gebruikt voor funding
    en employee counts die als strings kunnen komen van OpenAI.
    """
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


def _fetch_numeric_value_with_web_search(
    *,
    search_query: str,
    prompt: str,
    field_name: str,
    suffixes: Dict[str, int],
    log_label: str,
) -> Optional[int]:
    """Haal een numerieke waarde op via OpenAI Responses API met web search."""
    result = responses_json_with_sources(
        prompt,
        tools=[{"type": "web_search"}],
        tool_choice="auto",
        context=f"{log_label} for {search_query}",
    )
    if not result or "data" not in result:
        return None
    data = result["data"]
    if not isinstance(data, dict):
        return None
    return _parse_numeric_value(data.get(field_name), suffixes)


def fetch_openai_similar_companies(company_name: Optional[str] = None, domain: Optional[str] = None, limit: int = 10, use_web_search: bool = False) -> List[Dict]:
    """Haal vergelijkbare companies/competitors op via OpenAI API.
    
    BELANGRIJK: Dit vervangt Company Enrich API omdat OpenAI accurater bleek
    voor competitor identificatie. OpenAI kan beter onderscheid maken tussen
    echte competitors en suppliers/partners.
    
    Args:
        company_name: Company naam (bijv. 'Apple')
        domain: Company domein (bijv. 'apple.com')
        limit: Maximum aantal competitors om terug te geven
        use_web_search: Als True, gebruik web search voor actuele data (langzamer maar accurater)
        
    Returns:
        Lijst van competitor dictionaries met name, domain, website, industry, country
    """
    search_query = _build_search_query(company_name, domain)
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

    data = None
    
    # Gebruik web search alleen als expliciet gevraagd (voor performance)
    # Web search is accurater maar langzamer - gebruik voor expliciete refreshes
    if use_web_search:
        web_prompt = f"""Research the competitive landscape for "{search_query}" and identify their main competitors.

Search the web for recent information about:
1. Direct competitors in the same market
2. Companies offering similar products or services
3. Recent competitive developments or market shifts
4. Well-established competitors of similar scale

Based on your research, return a JSON object with a "competitors" array. Each competitor should have:
- name: Company name
- domain: Main domain (e.g., "apple.com" not "www.apple.com")
- website: Full website URL with https://
- industry: Primary industry
- country: Country where headquartered

Only include major, well-established competitors of similar scale.
Do NOT include the company itself, subsidiaries, resellers, or small regional players.
Use null for any field if information is not available.

Return valid JSON in this format:
{{
    "competitors": [
        {{"name": "...", "domain": "...", "website": "...", "industry": "...", "country": "..."}},
        ...
    ]
}}"""

        web_result = responses_json_with_sources(
            web_prompt,
            tools=[{"type": "web_search"}],
            tool_choice="auto",
            context=f"competitors for {search_query}"
        )
        
        if web_result and web_result.get("data"):
            data = web_result.get("data")
    
    # Fallback naar reguliere chat als web search niet werkte of niet gevraagd was
    if not data:
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
        result.append({
            "name": comp.get("name") or "Unknown",
            "domain": comp_domain,
            "website": comp.get("website") or (f"https://{comp_domain}" if comp_domain else None),
            "industry": comp.get("industry"),
            "country": comp.get("country"),
            "employees": None,
            "description": None,
        })
    
    return result[:limit]


def apply_company_data(company, api_data: Dict) -> None:
    """Pas bedrijfsdata uit een API-response toe op een Company record.

    BELANGRIJK: OpenAI-velden (description, employees, funding) krijgen ALTIJD voorrang
    op bestaande waarden. Dit is bewust: OpenAI data is accurater dan handmatige input.
    Basisvelden (industry, country) worden alleen gezet als ze nog niet bestaan.
    """
    if not company or not api_data:
        return
    
    if api_data.get("domain"):
        company.domain = api_data["domain"]
    if not company.website and api_data.get("website"):
        company.website = api_data["website"]
    
    # ALWAYS apply OpenAI fields (description, employees, funding) - these come from OpenAI, not Company Enrich
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


def fetch_openai_funding(company_name: Optional[str] = None, domain: Optional[str] = None, use_web_search: bool = False) -> Optional[int]:
    """Haal funding / market cap op via OpenAI.
    
    For publicly traded companies, returns market capitalization instead of funding.
    
    Args:
        company_name: Company name (e.g., 'Nike')
        domain: Company domain (e.g., 'nike.com')
        use_web_search: Als True, gebruik web search (langzamer maar accurater). Standaard False voor performance.
        
    Returns:
        Funding amount or market cap as integer (in base currency units), or None if not found/fails
    """
    search_query = _build_search_query(company_name, domain)
    if not search_query:
        return None
    
    prompt = f"""Find the current funding or market capitalization for the company "{search_query}".

IMPORTANT:
- For PRIVATELY HELD companies: Provide the total funding amount raised across all funding rounds.
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

    if use_web_search:
        # Gebruik web search voor actuele informatie
        web_prompt = f"""Research the company "{search_query}" and find their current funding or market capitalization.

Search the web for recent information about:
1. Recent funding rounds (seed, Series A, B, C, etc.) for private companies
2. Total funding raised across all rounds
3. Current market capitalization for publicly traded companies
4. Latest financial information

{prompt}"""

        return _fetch_numeric_value_with_web_search(
            search_query=search_query,
            field_name="funding",
            suffixes={"b": 1_000_000_000, "m": 1_000_000, "k": 1_000},
            log_label="funding/market cap",
            prompt=web_prompt,
        )
    else:
        # Gebruik reguliere chat API (sneller)
        data = chat_json(
            system_prompt="You are a helpful assistant that provides accurate company financial information. You must always respond with valid JSON only, no additional text.",
            user_prompt=prompt,
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=300,
            context=f"funding/market cap for {search_query}",
        )
        if not data:
            return None
        return _parse_numeric_value(data.get("funding"), {"b": 1_000_000_000, "m": 1_000_000, "k": 1_000})


def fetch_openai_team_size(company_name: Optional[str] = None, domain: Optional[str] = None, use_web_search: bool = False) -> Optional[int]:
    """Haal teamgrootte (aantal werknemers) op via OpenAI.
    
    Args:
        company_name: Company name (e.g., 'Nike')
        domain: Company domain (e.g., 'nike.com')
        use_web_search: Als True, gebruik web search (langzamer maar accurater). Standaard False voor performance.
        
    Returns:
        Number of employees as integer, or None if not found/fails
    """
    search_query = _build_search_query(company_name, domain)
    if not search_query:
        return None
    
    prompt = f"""Find the current number of employees (team size) for the company "{search_query}".

You must respond with valid JSON in this exact format:
{{
    "employees": 10000
}}

Where employees is the total number of employees as an integer. Use null if the information is not available."""

    if use_web_search:
        # Gebruik web search voor actuele informatie
        web_prompt = f"""Research the company "{search_query}" and find their current number of employees (team size).

Search the web for recent information about:
1. Current employee count
2. Recent hiring or layoff announcements
3. Company size information from official sources
4. Latest workforce statistics

{prompt}"""

        return _fetch_numeric_value_with_web_search(
            search_query=search_query,
            field_name="employees",
            suffixes={"m": 1_000_000, "k": 1_000},
            log_label="team size",
            prompt=web_prompt,
        )
    else:
        # Gebruik reguliere chat API (sneller)
        data = chat_json(
            system_prompt="You are a helpful assistant that provides accurate company information. You must always respond with valid JSON only, no additional text.",
            user_prompt=prompt,
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=200,
            context=f"team size for {search_query}",
        )
        if not data:
            return None
        return _parse_numeric_value(data.get("employees"), {"m": 1_000_000, "k": 1_000})


def fetch_openai_description(company_name: Optional[str] = None, domain: Optional[str] = None, use_web_search: bool = False) -> Optional[str]:
    """Haal een bedrijfsbeschrijving op via OpenAI.
    
    Args:
        company_name: Company name (e.g., 'Nike')
        domain: Company domain (e.g., 'nike.com')
        use_web_search: Als True, gebruik web search (langzamer maar accurater). Standaard False voor performance.
        
    Returns:
        Company description as string, or None if not found/fails
    """
    search_query = _build_search_query(company_name, domain)
    if not search_query:
        return None
    
    prompt = f"""Provide a comprehensive description of the company "{search_query}".

Provide a concise but informative description (2-4 sentences) in a professional tone suitable for a company profile page. Include:
1. What the company does
2. Its main products or services
3. Its market focus and positioning
4. Key differentiators or notable aspects

You must respond with valid JSON in this exact format:
{{
    "description": "Company description text here..."
}}

Use null for description if information is not available."""

    if use_web_search:
        # Gebruik web search voor actuele informatie
        web_prompt = f"""Research the company "{search_query}" and provide a comprehensive description.

Search the web for recent information about:
1. What the company does
2. Its main products or services
3. Its market focus and positioning
4. Key differentiators or notable aspects
5. Recent developments or news

Based on your research, provide a concise but informative description (2-4 sentences) in a professional tone suitable for a company profile page.

You must respond with valid JSON in this exact format:
{{
    "description": "Company description text here..."
}}

Use null for description if information is not available."""

        web_result = responses_json_with_sources(
            web_prompt,
            tools=[{"type": "web_search"}],
            tool_choice="auto",
            context=f"description for {search_query}",
        )
        data = web_result["data"] if web_result and web_result.get("data") else None
    else:
        # Gebruik reguliere chat API (sneller)
        data = chat_json(
            system_prompt="You are a helpful assistant that provides accurate company descriptions. You must always respond with valid JSON only, no additional text.",
            user_prompt=prompt,
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=300,
            context=f"description for {search_query}",
        )
    
    if not data:
        return None
    
    description = data.get("description")
    return None if not description or description.lower() in {"null", "none", "unknown", "n/a", ""} else description.strip()
