"""AI-powered competitive landscape generation service.

Generates short, analytical summaries of a company's competitive position
using OpenAI API based on company data and competitor information.
"""

import os
from typing import List, Optional
from models import Company

# Lazy initialization of OpenAI client
_client = None


def _get_openai_client():
    """Get or create OpenAI client instance (lazy initialization)."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import OpenAI
                _client = OpenAI(api_key=api_key)
            except Exception:
                # If OpenAI initialization fails, keep _client as None
                _client = False
        else:
            _client = False
    return _client if _client is not False else None


def generate_competitive_landscape(company: Company, competitors: List[Company]) -> Optional[str]:
    """Generate a competitive landscape summary using AI.
    
    Creates a 5-7 sentence analytical summary explaining:
    - Market position
    - Competitive pressures
    - Differentiation factors
    - Strategic considerations
    
    Args:
        company: Company model instance
        competitors: List of competitor Company instances
        
    Returns:
        Generated landscape text or None if API fails/unavailable
    """
    client = _get_openai_client()
    if not client or not company or not competitors:
        return None
    
    # Extract competitor names
    competitor_names = [c.name for c in competitors if c and c.name]
    
    # Extract industry names
    industries = []
    if company.industries:
        industries = [link.industry.name for link in company.industries if link and link.industry and link.industry.name]
    
    # Use headline as description (company.description doesn't exist in model)
    company_description = company.headline or ""
    
    # Build prompt
    prompt = f"""Generate a short, factual competitive landscape summary for the company '{company.name}'.

Base your answer ONLY on the data below.

Company description:
{company_description}

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
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )
        
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content.strip()
        return None
    except Exception:
        # Silently fail - don't break the app if AI is unavailable
        return None

