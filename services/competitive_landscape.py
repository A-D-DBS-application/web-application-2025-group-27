"""Service voor het genereren van een competitive landscape samenvatting."""

from typing import List, Optional

from models import Company
from services.openai_helpers import responses_json_with_sources


def generate_competitive_landscape(company: Company, competitors: List[Company]) -> Optional[str]:
    """Genereer een korte markt- en concurrentiesamenvatting voor een company.

    Gebruikt OpenAI Responses API met web search om actuele informatie te vinden
    over de competitive positie. Als de call faalt, retourneert None (caller
    moet fallback gebruiken).

    Args:
        company: het bedrijf waarvoor we de landscape maken
        competitors: lijst van competitor-companies

    Returns:
        Een tekstuele samenvatting van de competitive landscape, of None bij fout.
    """
    if not company or not competitors:
        return None
    
    # Lazy import om circulaire dependency te vermijden
    from utils.company_helpers import get_company_industries
    
    competitor_names = [c.name for c in competitors if c and c.name]
    industries = [ind.name for ind in get_company_industries(company) if ind and ind.name]
    
    # Bouw basiscontext voor de prompt
    company_desc = company.headline or ""
    industries_str = ", ".join(industries) if industries else "Not specified"
    competitors_str = ", ".join(competitor_names) if competitor_names else "None identified"
    
    # Gedeelde basisinhoud voor de prompt
    base_content = f"""Company description:
{company_desc}

Industries:
{industries_str}

Known competitors:
{competitors_str}

Please produce 5–7 sentences explaining:
- the type of market this company operates in
- how it positions itself relative to competitors
- what the main competitive pressures are
- what differentiates this company
- any risks or strategic considerations

Keep the tone: clear, analytical, crisp, and business-focused."""
    
    # Gebruik uitsluitend web search voor deze samenvatting (voor actuele data)
    web_prompt = f"""Research the competitive landscape for '{company.name}' and generate a short, factual summary.

Search the web for recent information about:
1. Current market trends in their industry
2. Recent competitive developments
3. Market positioning and differentiation
4. Strategic challenges or opportunities

{base_content}

Return ONLY the summary text, no JSON or markdown."""

    web_result = responses_json_with_sources(
        web_prompt,
        tools=[{"type": "web_search"}],
        tool_choice="auto",
        context=f"competitive landscape for {company.name}",
    )
    if not web_result or not web_result.get("data"):
        return None
    # Responses API kan verschillende data formats retourneren - probeer alle mogelijkheden
    data = web_result.get("data", {})
    summary = data.get("summary") or data.get("text") or (str(data) if isinstance(data, dict) else "")
    return summary.strip() if summary and summary.strip() else None
