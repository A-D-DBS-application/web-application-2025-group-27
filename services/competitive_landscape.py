"""Competitive landscape AI service - generates market context summaries."""

import os
from typing import List, Optional

from models import Company

_client = None


def _get_openai_client():
    """Get OpenAI client (cached singleton)."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import OpenAI
                _client = OpenAI(api_key=api_key)
            except Exception:
                _client = False
        else:
            _client = False
    return _client if _client is not False else None


def generate_competitive_landscape(company: Company, competitors: List[Company]) -> Optional[str]:
    """Generate a competitive landscape summary for a company."""
    client = _get_openai_client()
    if not client or not company or not competitors:
        return None
    
    # Gather context
    from utils.company_helpers import get_company_industries
    competitor_names = [c.name for c in competitors if c and c.name]
    industries = [ind.name for ind in get_company_industries(company) if ind and ind.name]
    
    prompt = f"""Generate a short, factual competitive landscape summary for the company '{company.name}'.

Base your answer ONLY on the data below.

Company description:
{company.headline or ""}

Industries:
{", ".join(industries) if industries else "Not specified"}

Known competitors:
{", ".join(competitor_names) if competitor_names else "None identified"}

Please produce 5–7 sentences explaining:
- the type of market this company operates in
- how it positions itself relative to competitors
- what the main competitive pressures are
- what differentiates this company
- any risks or strategic considerations

Keep the tone: clear, analytical, crisp, and business-focused."""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )
        return resp.choices[0].message.content.strip() if resp.choices else None
    except Exception:
        return None
