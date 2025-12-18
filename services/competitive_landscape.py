"""Service voor het genereren van een competitive landscape samenvatting."""

from typing import List, Optional

from models import Company
from services.openai_helpers import chat_json, responses_json_with_sources


def generate_competitive_landscape(company: Company, competitors: List[Company], use_web_search: bool = False) -> Optional[str]:
    """Genereer een korte markt- en concurrentiesamenvatting voor een company.

    Args:
        company: het bedrijf waarvoor we de landscape maken
        competitors: lijst van competitor-companies
        use_web_search: Als True, gebruik web search (langzamer maar accurater). Standaard False voor performance.

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
    
    if use_web_search:
        # Gebruik web search voor actuele data
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
    else:
        # Gebruik reguliere chat API (sneller) - haal direct text response op
        prompt = f"""{base_content}

Return ONLY the summary text, no JSON or markdown."""
        
        # Gebruik chat_json maar met response_format=None om plain text te krijgen
        # We moeten de raw response ophalen, niet geparsed JSON
        from services.openai_helpers import get_openai_client
        client = get_openai_client()
        if not client:
            return None
        
        try:
            payload = [
                {"role": "system", "content": "You are a business analyst. Provide clear, analytical, and business-focused competitive intelligence summaries. Always respond with plain text only, no JSON or markdown."},
                {"role": "user", "content": prompt}
            ]
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=payload,
                temperature=0.3,
                max_tokens=400,
                # Geen response_format - dit geeft plain text
            )
            message = resp.choices[0].message if resp and resp.choices else None
            summary = message.content if message and message.content else None
            return summary.strip() if summary and summary.strip() else None
        except Exception:
            return None
