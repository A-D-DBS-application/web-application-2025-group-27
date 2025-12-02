"""Market positioning AI service - generates structured insights for a company."""

import json
import os
from typing import Optional

from app import db
from models import Company, MarketPositioning


def _get_openai_client():
    """Get OpenAI client if API key is configured."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def _clean_json_response(content: str) -> str:
    """Clean potential markdown from JSON response."""
    if not content:
        return ""
    content = content.strip()
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.startswith("json"):
            content = content[4:]
    return content.strip()


def generate_market_positioning(company: Company) -> Optional[MarketPositioning]:
    """Generate or return cached market positioning for a company."""
    if not company:
        return None
    
    # Return cached if exists
    if company.market_positioning:
        return company.market_positioning
    
    # Gather context data
    from utils.company_helpers import get_company_industries, get_company_competitors
    industries = [ind.name for ind in get_company_industries(company) if ind and ind.name]
    competitors = [c.name for c in get_company_competitors(company) if c and c.name]
    
    # Build prompt
    prompt = f"""You are an expert in market positioning and strategic analysis.
Return ONLY valid JSON with these keys:
- value_proposition
- competitive_edge
- brand_perception
- key_segments
- weaknesses
- opportunity_areas
- summary

Each key contains 2-4 sentences of analytical, precise text.

Input:
Company name: {company.name}
Description: {company.headline or "Not available"}
Industries: {", ".join(industries) if industries else "Not specified"}
Competitors: {", ".join(competitors) if competitors else "None identified"}

Your output MUST be pure JSON. No markdown, no code blocks."""

    # Try to generate via OpenAI
    data = {}
    client = _get_openai_client()
    
    if client:
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=800
            )
            content = _clean_json_response(
                resp.choices[0].message.content if resp.choices else ""
            )
            data = json.loads(content)
        except Exception:
            pass
    
    # Create MarketPositioning record
    default_text = "Analysis not available."
    mp = MarketPositioning(
        company_id=company.id,
        value_proposition=data.get("value_proposition", default_text),
        competitive_edge=data.get("competitive_edge", default_text),
        brand_perception=data.get("brand_perception", default_text),
        key_segments=data.get("key_segments", default_text),
        weaknesses=data.get("weaknesses", default_text),
        opportunity_areas=data.get("opportunity_areas", default_text),
        summary=data.get("summary", "Market positioning analysis is being prepared."),
    )
    
    db.session.add(mp)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None
    
    return mp
