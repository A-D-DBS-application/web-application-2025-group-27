"""Signals service - detects COMPETITOR changes and generates AI-powered alerts.

IMPORTANT: This system generates signals ONLY for competitors, never for the main company.
"""

import json
import os
from typing import Optional

from app import db
from models import Company, CompanySignal, CompanySnapshot


# =============================================================================
# OpenAI Client
# =============================================================================

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
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


# =============================================================================
# Default Snapshot Structure
# =============================================================================

def get_default_snapshot() -> dict:
    """Return default snapshot structure."""
    return {
        "basic": {
            "name": "",
            "domain": "",
            "country": "",
            "industries": [],
            "description_summary": ""
        },
        "organization": {
            "employee_size": "unknown",
            "locations": []
        },
        "hiring_focus": {
            "engineering": 0,
            "data": 0,
            "product": 0,
            "design": 0,
            "marketing": 0,
            "sales": 0,
            "operations": 0,
            "ai_ml_roles": 0
        },
        "strategic_profile": {
            "primary_markets": [],
            "product_themes": [],
            "target_segments": [],
            "notable_strengths": [],
            "risk_factors": []
        }
    }


def _get_employee_size_bucket(count: int) -> str:
    """Convert employee count to size bucket."""
    if not count or count <= 0:
        return "unknown"
    if count <= 10:
        return "1-10"
    if count <= 50:
        return "11-50"
    if count <= 200:
        return "51-200"
    if count <= 500:
        return "201-500"
    if count <= 1000:
        return "501-1000"
    if count <= 5000:
        return "1000-5000"
    return "5000+"


# =============================================================================
# Competitor Snapshot Management
# =============================================================================

def build_competitor_snapshot(company: Company, competitor: Company, force_ai: bool = False) -> dict:
    """Build a structured competitor profile snapshot.
    
    Uses OpenAI to generate a rich profile from available data.
    Falls back to basic data extraction if AI is unavailable.
    """
    if not competitor:
        return get_default_snapshot()
    
    # Gather competitor's industries
    industries = sorted([
        link.industry.name
        for link in competitor.industries
        if link.industry and link.industry.name
    ])
    
    # Try to reuse AI-generated profile from last snapshot (if not forcing refresh)
    if not force_ai:
        last_snap = load_last_competitor_snapshot(company, competitor)
        if last_snap:
            try:
                old_data = json.loads(last_snap.data)
                # Check if it has the new structure
                if "basic" in old_data and "strategic_profile" in old_data:
                    # Update basic fields that might have changed
                    old_data["basic"]["industries"] = industries
                    old_data["basic"]["country"] = competitor.country or ""
                    old_data["organization"]["employee_size"] = _get_employee_size_bucket(
                        competitor.number_of_employees
                    )
                    return old_data
            except Exception:
                pass
    
    # Build structured data for the prompt
    structured_data = {
        "employees": competitor.number_of_employees,
        "funding": competitor.funding,
        "country": competitor.country,
        "industries": industries,
    }
    
    # Try AI-powered snapshot generation
    client = _get_openai_client()
    if client:
        ai_snapshot = _generate_ai_snapshot(client, company, competitor, industries, structured_data)
        if ai_snapshot:
            return ai_snapshot
    
    # Fallback: build basic snapshot without AI
    return _build_basic_snapshot(competitor, industries)


def _generate_ai_snapshot_with_web_search(client, company: Company, competitor: Company, industries: list, structured_data: dict) -> Optional[dict]:
    """Generate AI-powered competitor snapshot using Responses API with web search.
    
    This uses OpenAI's web_search tool to research the competitor online.
    """
    prompt = f"""Research the company "{competitor.name}" (website: {competitor.domain or 'unknown'}) 
and create a competitive intelligence profile.

Search the web for recent information about:
1. Their current products and services
2. Recent news, funding, or acquisitions
3. Company size and growth
4. Key markets and target customers
5. Notable strengths and competitive advantages
6. Any risks or challenges they face

Based on your research, return a JSON profile in this exact format:

{{
  "basic": {{
    "name": "{competitor.name}",
    "domain": "{competitor.domain or ''}",
    "country": "{competitor.country or ''}",
    "industries": {json.dumps(industries)},
    "description_summary": "2-3 sentence summary based on your research"
  }},
  "organization": {{
    "employee_size": "unknown" | "1-10" | "11-50" | "51-200" | "201-500" | "501-1000" | "1000-5000" | "5000+",
    "locations": ["list of office locations if found"]
  }},
  "hiring_focus": {{
    "engineering": 0-5,
    "data": 0-5,
    "product": 0-5,
    "design": 0-5,
    "marketing": 0-5,
    "sales": 0-5,
    "operations": 0-5,
    "ai_ml_roles": 0-5
  }},
  "strategic_profile": {{
    "primary_markets": ["markets they serve"],
    "product_themes": ["main product categories"],
    "target_segments": ["customer segments"],
    "notable_strengths": ["competitive advantages"],
    "risk_factors": ["challenges or risks"]
  }}
}}

Context: This profile is for {company.name} who is tracking {competitor.name} as a competitor.

IMPORTANT: Return ONLY valid JSON, no markdown or explanation."""

    try:
        # Try using the Responses API with web search
        resp = client.responses.create(
            model="gpt-4o",
            input=prompt,
            tools=[{"type": "web_search"}],
            tool_choice="auto"
        )
        
        # Extract text from response
        content = ""
        for item in resp.output:
            if hasattr(item, 'content'):
                for c in item.content:
                    if hasattr(c, 'text'):
                        content += c.text
        
        content = _clean_json_response(content)
        if content:
            return json.loads(content)
    except Exception as e:
        # Log error but don't fail - fall back to regular method
        print(f"Web search failed for {competitor.name}: {e}")
    
    return None


def _generate_ai_snapshot(client, company: Company, competitor: Company, industries: list, structured_data: dict) -> Optional[dict]:
    """Generate AI-powered competitor snapshot.
    
    First tries web search for richer data, falls back to basic prompt.
    """
    # Try web search first for richer data
    web_result = _generate_ai_snapshot_with_web_search(client, company, competitor, industries, structured_data)
    if web_result:
        return _validate_snapshot(web_result)
    
    # Fallback to basic prompt without web search
    prompt = f"""You are an expert in competitive intelligence. Your task is to generate a
structured factual competitor profile using ONLY the information provided.
The output will be stored as part of a snapshot and compared over time to
detect changes.

IMPORTANT:
- Output MUST be valid JSON only.
- NEVER invent specific facts, numbers, names, products, employees, or
  technologies that are not implied by the provided data.
- If uncertain, return "unknown" or empty arrays.
- Keep all fields present, never remove keys.

INPUT DATA:
- Competitor name: {competitor.name}
- Description: {competitor.headline or 'N/A'}
- Industries: {', '.join(industries) if industries else 'N/A'}
- Domain / Website: {competitor.domain or 'N/A'}
- Any structured data (JSON): {json.dumps(structured_data)}
- User company for context: {company.name}

TASK:
From the provided information above, extract or infer a stable competitor
baseline profile that can be stored in a snapshot and later compared to detect
organizational, hiring, and strategic changes.

RETURN STRICT JSON IN THIS EXACT FORMAT:

{{
  "basic": {{
    "name": "",
    "domain": "",
    "country": "",
    "industries": [],
    "description_summary": ""
  }},

  "organization": {{
    "employee_size": "unknown" | "1-10" | "11-50" | "51-200" | "201-500" |
                      "501-1000" | "1000-5000" | "5000+",
    "locations": []
  }},

  "hiring_focus": {{
    "engineering": 0,
    "data": 0,
    "product": 0,
    "design": 0,
    "marketing": 0,
    "sales": 0,
    "operations": 0,
    "ai_ml_roles": 0
  }},

  "strategic_profile": {{
    "primary_markets": [],
    "product_themes": [],
    "target_segments": [],
    "notable_strengths": [],
    "risk_factors": []
  }}
}}

RULES:
- Infer trends only if clearly implied by the input.
- Use number scores (0–5) in hiring_focus to indicate emphasis.
- Avoid any hallucinations or made-up data.
- Preserve structure exactly.
- If the input is very limited, return minimal but valid JSON."""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800
        )
        content = _clean_json_response(
            resp.choices[0].message.content if resp.choices else ""
        )
        data = json.loads(content)
        return _validate_snapshot(data)
    except Exception:
        return None


def _validate_snapshot(data: dict) -> dict:
    """Validate and ensure all required keys exist in snapshot."""
    default = get_default_snapshot()
    
    # Ensure basic section
    if "basic" not in data:
        data["basic"] = default["basic"]
    for key in default["basic"]:
        if key not in data["basic"]:
            data["basic"][key] = default["basic"][key]
    
    # Ensure organization section
    if "organization" not in data:
        data["organization"] = default["organization"]
    for key in default["organization"]:
        if key not in data["organization"]:
            data["organization"][key] = default["organization"][key]
    
    # Ensure hiring_focus section with valid scores
    if "hiring_focus" not in data:
        data["hiring_focus"] = default["hiring_focus"]
    for key in default["hiring_focus"]:
        val = data.get("hiring_focus", {}).get(key, 0)
        data["hiring_focus"][key] = max(0, min(5, int(val))) if isinstance(val, (int, float)) else 0
    
    # Ensure strategic_profile section
    if "strategic_profile" not in data:
        data["strategic_profile"] = default["strategic_profile"]
    for key in default["strategic_profile"]:
        if key not in data["strategic_profile"]:
            data["strategic_profile"][key] = []
    
    return data


def _build_basic_snapshot(competitor: Company, industries: list) -> dict:
    """Build basic snapshot without AI (fallback)."""
    return {
        "basic": {
            "name": competitor.name or "",
            "domain": competitor.domain or "",
            "country": competitor.country or "",
            "industries": industries,
            "description_summary": (competitor.headline or "")[:200]
        },
        "organization": {
            "employee_size": _get_employee_size_bucket(competitor.number_of_employees),
            "locations": [competitor.country] if competitor.country else []
        },
        "hiring_focus": {
            "engineering": 0,
            "data": 0,
            "product": 0,
            "design": 0,
            "marketing": 0,
            "sales": 0,
            "operations": 0,
            "ai_ml_roles": 0
        },
        "strategic_profile": {
            "primary_markets": [],
            "product_themes": [],
            "target_segments": [],
            "notable_strengths": [],
            "risk_factors": []
        }
    }


def load_last_competitor_snapshot(company: Company, competitor: Company) -> Optional[CompanySnapshot]:
    """Load the most recent snapshot for a specific competitor."""
    if not company or not competitor:
        return None
    return (
        CompanySnapshot.query
        .filter_by(company_id=company.id, competitor_id=competitor.id)
        .order_by(CompanySnapshot.created_at.desc())
        .first()
    )


def save_competitor_snapshot(company: Company, competitor: Company, snapshot: dict) -> CompanySnapshot:
    """Save a new snapshot for a competitor."""
    snap = CompanySnapshot(
        company_id=company.id,
        competitor_id=competitor.id,
        data=json.dumps(snapshot)
    )
    db.session.add(snap)
    db.session.commit()
    return snap


# =============================================================================
# Diff Computation
# =============================================================================

def compute_diff(old: Optional[dict], new: dict) -> dict:
    """Compute diff between old and new snapshots."""
    if not old:
        return {"is_initial": True}
    
    diff = {}
    
    # Handle both old format (flat) and new format (nested)
    old_basic = old.get("basic", old)
    new_basic = new.get("basic", new)
    old_org = old.get("organization", old)
    new_org = new.get("organization", new)
    old_hiring = old.get("hiring_focus", {})
    new_hiring = new.get("hiring_focus", {})
    old_strategic = old.get("strategic_profile", {})
    new_strategic = new.get("strategic_profile", {})
    
    # Employee size change
    old_size = old_org.get("employee_size", old.get("employees", "unknown"))
    new_size = new_org.get("employee_size", new.get("employees", "unknown"))
    if old_size != new_size and old_size != "unknown":
        diff["employee_size_change"] = {"old": old_size, "new": new_size}
    
    # Industry changes
    old_ind = set(old_basic.get("industries", []))
    new_ind = set(new_basic.get("industries", []))
    if old_ind != new_ind:
        if new_ind - old_ind:
            diff["new_industries"] = list(new_ind - old_ind)
        if old_ind - new_ind:
            diff["dropped_industries"] = list(old_ind - new_ind)
    
    # Country change
    old_country = old_basic.get("country", old.get("country", ""))
    new_country = new_basic.get("country", new.get("country", ""))
    if old_country and old_country != new_country:
        diff["country_changed"] = {"old": old_country, "new": new_country}
    
    # Hiring focus changes
    if old_hiring and new_hiring:
        hiring_diff = {}
        for key in ["engineering", "data", "product", "design", "marketing", "sales", "operations", "ai_ml_roles"]:
            old_val = old_hiring.get(key, 0)
            new_val = new_hiring.get(key, 0)
            if old_val != new_val:
                hiring_diff[key] = {"old": old_val, "new": new_val, "change": new_val - old_val}
        if hiring_diff:
            diff["hiring_focus_change"] = hiring_diff
    
    # Strategic profile changes
    for field in ["primary_markets", "product_themes", "target_segments"]:
        old_list = set(old_strategic.get(field, []))
        new_list = set(new_strategic.get(field, []))
        if old_list != new_list:
            diff[f"{field}_changed"] = {
                "added": list(new_list - old_list),
                "removed": list(old_list - new_list)
            }
    
    return diff


MEANINGFUL_DIFF_KEYS = [
    "employee_size_change", "new_industries", "dropped_industries",
    "country_changed", "hiring_focus_change",
    "primary_markets_changed", "product_themes_changed", "target_segments_changed"
]


# =============================================================================
# Competitor Signal Generation
# =============================================================================

def generate_signals_for_competitor(company: Company, competitor: Company, diff: dict) -> list:
    """Generate AI signals from a competitor diff.
    
    IMPORTANT: All signals MUST have competitor_id set.
    """
    if diff.get("is_initial") or not diff:
        return []
    
    if not any(k in diff for k in MEANINGFUL_DIFF_KEYS):
        return []
    
    client = _get_openai_client()
    if not client:
        return _generate_simple_competitor_signals(company, competitor, diff)
    
    prompt = f"""You are an analyst for a competitive intelligence tool.
You receive a "diff" describing changes in a COMPETITOR's organizational state.

Your task:
- Interpret the diff
- Decide which changes are meaningful for competitive analysis
- Categorize each signal into one of three categories: hiring, product, or funding
- Return them as an array of structured "signals"

INPUT:
- Your company is tracking this competitor: {competitor.name}
- Competitor description: {competitor.headline or 'N/A'}
- Diff (JSON): {json.dumps(diff)}

OUTPUT FORMAT (MUST BE VALID JSON, NO MARKDOWN):

{{
  "signals": [
    {{
      "signal_type": "headcount_change" | "industry_shift" | "hiring_shift" | "market_expansion" | "strategic_change" | "product_launch" | "funding_round",
      "category": "hiring" | "product" | "funding",
      "severity": "low" | "medium" | "high",
      "message": "Short UI-ready title about the competitor (~1 sentence)",
      "details": "2-4 sentence explanation of why this competitor change matters to you.",
      "source_url": "Optional URL to news article, company page, or other source (leave empty if not available)"
    }}
  ]
}}

Category Rules:
- "hiring": New roles/jobs posted, key hires/appointments (e.g., "Adidas has hired a new Head of Sales"), team expansion
- "product": New product launches, feature releases, integrations, major product updates
- "funding": Funding rounds, investments, investor announcements, round types (pre-seed, seed, Series A, etc.)

Signal Type Mapping:
- hiring_shift, headcount_change → category: "hiring"
- product_launch, market_expansion (product-related) → category: "product"  
- funding_round → category: "funding"
- Other strategic changes → infer category from context

Rules:
- Focus on what this means COMPETITIVELY for the user watching this competitor.
- Severity should reflect potential competitive impact.
- Be specific about the competitor name in messages.
- Always assign a category (hiring, product, or funding).
- Return empty signals array if changes are trivial."""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=600
        )
        content = _clean_json_response(
            resp.choices[0].message.content if resp.choices else ""
        )
        data = json.loads(content)
        signals_data = data.get("signals", [])
        
        signals = []
        for s in signals_data:
            # Determine category from signal type if not provided
            category = s.get("category")
            if not category:
                signal_type = s.get("signal_type", "")
                if "hiring" in signal_type or "headcount" in signal_type:
                    category = "hiring"
                elif "funding" in signal_type:
                    category = "funding"
                elif "product" in signal_type or "launch" in signal_type:
                    category = "product"
                else:
                    category = "product"  # Default fallback
            
            sig = CompanySignal(
                company_id=company.id,
                competitor_id=competitor.id,
                signal_type=s.get("signal_type", "strategic_change"),
                category=category,
                severity=s.get("severity", "low"),
                message=s.get("message", f"Change detected for {competitor.name}"),
                details=s.get("details", ""),
                source_url=s.get("source_url") or None,
                is_new=True
            )
            db.session.add(sig)
            signals.append(sig)
        
        db.session.commit()
        return signals
    except Exception:
        return _generate_simple_competitor_signals(company, competitor, diff)


def _generate_simple_competitor_signals(company: Company, competitor: Company, diff: dict) -> list:
    """Generate simple competitor signals without AI."""
    signals = []
    comp_name = competitor.name or "Competitor"
    
    if "employee_size_change" in diff:
        change = diff["employee_size_change"]
        sig = CompanySignal(
            company_id=company.id,
            competitor_id=competitor.id,
            signal_type="headcount_change",
            category="hiring",
            severity="medium",
            message=f"{comp_name} changed size from {change['old']} to {change['new']}",
            details=f"Employee size bracket changed, indicating organizational growth or contraction.",
            is_new=True
        )
        db.session.add(sig)
        signals.append(sig)
    
    if "new_industries" in diff:
        sig = CompanySignal(
            company_id=company.id,
            competitor_id=competitor.id,
            signal_type="industry_shift",
            category="product",
            severity="medium",
            message=f"{comp_name} expanding into new industries",
            details=f"Added industries: {', '.join(diff['new_industries'])}",
            is_new=True
        )
        db.session.add(sig)
        signals.append(sig)
    
    if "hiring_focus_change" in diff:
        changes = diff["hiring_focus_change"]
        growing = [k for k, v in changes.items() if v.get("change", 0) > 0]
        if growing:
            sig = CompanySignal(
                company_id=company.id,
                competitor_id=competitor.id,
                signal_type="hiring_shift",
                category="hiring",
                severity="medium",
                message=f"{comp_name} increasing focus on {', '.join(growing[:3])}",
                details=f"Hiring emphasis has shifted, suggesting strategic priorities.",
                is_new=True
            )
            db.session.add(sig)
            signals.append(sig)
    
    if "primary_markets_changed" in diff:
        change = diff["primary_markets_changed"]
        if change.get("added"):
            sig = CompanySignal(
                company_id=company.id,
                competitor_id=competitor.id,
                signal_type="market_expansion",
                category="product",
                severity="high",
                message=f"{comp_name} entering new markets: {', '.join(change['added'][:3])}",
                details=f"Market expansion detected, potential competitive threat.",
                is_new=True
            )
            db.session.add(sig)
            signals.append(sig)
    
    db.session.commit()
    return signals


# =============================================================================
# Unread Signal Counting
# =============================================================================

def count_unread_signals(company: Company) -> int:
    """Count unread (new) competitor signals for a company."""
    if not company:
        return 0
    return (
        CompanySignal.query
        .filter_by(company_id=company.id, is_new=True)
        .filter(CompanySignal.competitor_id.isnot(None))
        .count()
    )


def count_unread_signals_by_category(company: Company) -> dict:
    """Count unread signals grouped by category.
    
    Returns dict with keys: 'hiring', 'product', 'funding', 'total'
    """
    if not company:
        return {"hiring": 0, "product": 0, "funding": 0, "total": 0}
    
    signals = (
        CompanySignal.query
        .filter_by(company_id=company.id, is_new=True)
        .filter(CompanySignal.competitor_id.isnot(None))
        .all()
    )
    
    counts = {"hiring": 0, "product": 0, "funding": 0, "total": len(signals)}
    for sig in signals:
        category = sig.category or "product"  # Default to product if not set
        if category in counts:
            counts[category] += 1
    
    return counts


def mark_signals_as_read(company: Company) -> int:
    """Mark all competitor signals as read for a company. Returns count marked."""
    if not company:
        return 0
    count = (
        CompanySignal.query
        .filter_by(company_id=company.id, is_new=True)
        .filter(CompanySignal.competitor_id.isnot(None))
        .update({"is_new": False})
    )
    db.session.commit()
    return count


def get_competitor_signals(company: Company, category: Optional[str] = None) -> list:
    """Get all competitor signals for a company, optionally filtered by category.
    
    Args:
        company: The company whose signals to retrieve
        category: Optional filter by category ('hiring', 'product', 'funding')
    """
    if not company:
        return []
    
    query = (
        CompanySignal.query
        .filter_by(company_id=company.id)
        .filter(CompanySignal.competitor_id.isnot(None))
    )
    
    if category:
        query = query.filter_by(category=category)
    
    return list(
        query.order_by(CompanySignal.created_at.desc()).all()
    )


def get_all_competitor_snapshots(company: Company) -> dict:
    """Get the latest snapshot data for all competitors of a company.
    
    Returns a dict mapping competitor_id -> snapshot data dict
    """
    if not company:
        return {}
    
    snapshots = {}
    for link in company.competitors:
        if not link or not link.competitor:
            continue
        competitor = link.competitor
        snap = load_last_competitor_snapshot(company, competitor)
        if snap:
            try:
                snapshots[str(competitor.id)] = {
                    "competitor_name": competitor.name,
                    "data": json.loads(snap.data),
                    "created_at": snap.created_at.isoformat() if snap.created_at else None
                }
            except Exception:
                pass
    return snapshots


# =============================================================================
# Main Orchestrator: Refresh Competitor Signals
# =============================================================================

def refresh_competitor_signals(company: Company, force_ai: bool = False) -> list:
    """Refresh signals for ALL competitors of a company.
    
    This is the main entry point. It:
    1. Iterates through all competitors
    2. Builds/compares snapshots (with AI-powered profiling)
    3. Generates signals for meaningful changes
    4. Returns all competitor signals
    
    Args:
        company: The company whose competitors to analyze
        force_ai: If True, regenerate AI profiles even if cached
    
    NO signals are generated for the company itself.
    """
    if not company:
        return []
    
    for link in company.competitors:
        if not link or not link.competitor:
            continue
        
        competitor = link.competitor
        
        # Build current snapshot (may use AI)
        current = build_competitor_snapshot(company, competitor, force_ai=force_ai)
        
        # Load last snapshot
        last_snap = load_last_competitor_snapshot(company, competitor)
        old_data = json.loads(last_snap.data) if last_snap else None
        
        # Compute diff
        diff = compute_diff(old_data, current)
        
        # Initial snapshot: save and continue (no signals on first run)
        if diff.get("is_initial"):
            save_competitor_snapshot(company, competitor, current)
            continue
        
        # Check for meaningful changes
        if any(k in diff for k in MEANINGFUL_DIFF_KEYS):
            # Save new snapshot
            save_competitor_snapshot(company, competitor, current)
            # Generate signals
            generate_signals_for_competitor(company, competitor, diff)
    
    # Return all competitor signals (including previously generated ones)
    return get_competitor_signals(company)
