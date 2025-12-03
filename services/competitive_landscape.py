"""Competitive landscape AI service - generates market context summaries."""

from typing import List, Optional

from models import Company
from services.openai_helpers import chat_text


def generate_competitive_landscape(company: Company, competitors: List[Company]) -> Optional[str]:
    """Generate a competitive landscape summary for a company."""
    if not company or not competitors:
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

    return chat_text(
        user_prompt=prompt,
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=300,
        context=f"competitive landscape for {company.name}",
    ) or None
