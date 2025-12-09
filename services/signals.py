"""Signals service - detects COMPETITOR changes and generates AI-powered alerts.

IMPORTANT: This system generates signals ONLY for competitors, never for the main company.
"""

import json
from copy import deepcopy
from typing import Optional

from app import db
from models import Company, CompanySignal, CompanySnapshot
from services.openai_helpers import chat_json, responses_json


SNAPSHOT_TEMPLATE = {
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

LIST_FIELDS = {
    "basic": ("industries",),
    "organization": ("locations",),
    "strategic_profile": tuple(SNAPSHOT_TEMPLATE["strategic_profile"].keys()),
}


def get_default_snapshot() -> dict:
    """Return default snapshot structure."""
    return deepcopy(SNAPSHOT_TEMPLATE)


SIZE_BUCKETS = [
    (10, "1-10"),
    (50, "11-50"),
    (200, "51-200"),
    (500, "201-500"),
    (1000, "501-1000"),
    (5000, "1000-5000"),
]


def _get_employee_size_bucket(count: int) -> str:
    """Convert employee count to size bucket."""
    if not count or count <= 0:
        return "unknown"
    for limit, label in SIZE_BUCKETS:
        if count <= limit:
            return label
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
    
    industries = sorted([link.industry.name for link in getattr(competitor, "industries", []) or []
                        if link.industry and link.industry.name])
    
    if not force_ai:
        cached = _reuse_cached_snapshot(company, competitor, industries)
        if cached:
            return cached
    
    structured_data = {"employees": competitor.number_of_employees, "funding": competitor.funding,
                       "country": competitor.country, "industries": industries}
    
    ai_snapshot = _generate_ai_snapshot(company, competitor, industries, structured_data)
    return ai_snapshot if ai_snapshot else _build_basic_snapshot(competitor, industries)


def _reuse_cached_snapshot(company: Company, competitor: Company, industries: list) -> Optional[dict]:
    """Attempt to reuse latest snapshot for faster loads."""
    last_snap = load_last_competitor_snapshot(company, competitor)
    old_data = _snapshot_dict(last_snap)
    if not old_data or "basic" not in old_data or "strategic_profile" not in old_data:
        return None
    old_data["basic"]["industries"] = industries
    old_data["basic"]["country"] = competitor.country or ""
    org = old_data.setdefault("organization", {})
    org["employee_size"] = _get_employee_size_bucket(competitor.number_of_employees)
    return old_data


def _generate_ai_snapshot(company: Company, competitor: Company, industries: list, structured_data: dict) -> Optional[dict]:
    """Generate AI-powered competitor snapshot, with web search fallback."""
    web_prompt = f"""Research the company "{competitor.name}" (website: {competitor.domain or 'unknown'}) and create a competitive intelligence profile.

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

    web_result = responses_json(web_prompt, tools=[{"type": "web_search"}], tool_choice="auto", context=f"web search snapshot for {competitor.name}")
    if web_result:
        return _validate_snapshot(web_result)

    prompt = f"""You are an expert in competitive intelligence. Your task is to generate a structured factual competitor profile using ONLY the information provided.
The output will be stored as part of a snapshot and compared over time to detect changes.

IMPORTANT:
- Output MUST be valid JSON only.
- NEVER invent specific facts, numbers, names, products, employees, or technologies that are not implied by the provided data.
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
From the provided information above, extract or infer a stable competitor baseline profile that can be stored in a snapshot and later compared to detect organizational, hiring, and strategic changes.

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
    "employee_size": "unknown" | "1-10" | "11-50" | "51-200" | "201-500" | "501-1000" | "1000-5000" | "5000+",
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

    data = chat_json(user_prompt=prompt, model="gpt-4o-mini", temperature=0.3, max_tokens=800, context=f"snapshot for {competitor.name}")
    return _validate_snapshot(data) if data else None


def _validate_snapshot(data: dict) -> dict:
    """Validate and ensure all required keys exist in snapshot."""
    snapshot = get_default_snapshot()
    if not isinstance(data, dict):
        return snapshot
    for section in snapshot:
        incoming = data.get(section)
        if isinstance(incoming, dict):
            snapshot[section].update(incoming)
    for section, fields in LIST_FIELDS.items():
        section_data = snapshot[section]
        for field in fields:
            val = section_data.get(field)
            section_data[field] = val if isinstance(val, list) else []
    hiring = snapshot["hiring_focus"]
    for key in hiring:
        val = hiring[key]
        hiring[key] = max(0, min(5, int(val))) if isinstance(val, (int, float)) else 0
    return snapshot


def _build_basic_snapshot(competitor: Company, industries: list) -> dict:
    """Build basic snapshot without AI (fallback)."""
    snapshot = get_default_snapshot()
    snapshot["basic"].update({
        "name": competitor.name or "",
        "domain": competitor.domain or "",
        "country": competitor.country or "",
        "industries": industries,
        "description_summary": (competitor.headline or "")[:200],
    })
    snapshot["organization"]["employee_size"] = _get_employee_size_bucket(competitor.number_of_employees)
    snapshot["organization"]["locations"] = [competitor.country] if competitor.country else []
    return snapshot


def load_last_competitor_snapshot(company: Company, competitor: Company) -> Optional[CompanySnapshot]:
    """Load the most recent snapshot for a specific competitor."""
    if not company or not competitor:
        return None
    return CompanySnapshot.query.filter_by(company_id=company.id, competitor_id=competitor.id).order_by(
        CompanySnapshot.created_at.desc()).first()


def save_competitor_snapshot(company: Company, competitor: Company, snapshot: dict) -> CompanySnapshot:
    """Save a new snapshot for a competitor."""
    snap = CompanySnapshot()
    snap.company_id = company.id
    snap.competitor_id = competitor.id
    snap.data = json.dumps(snapshot)
    db.session.add(snap)
    db.session.commit()
    return snap


def _snapshot_dict(snapshot: Optional[CompanySnapshot]) -> Optional[dict]:
    if not snapshot:
        return None
    try:
        return json.loads(snapshot.data)
    except Exception:
        return None


# =============================================================================
# Diff Computation
# =============================================================================

def compute_diff(old: Optional[dict], new: dict) -> dict:
    """Compute diff between old and new snapshots."""
    if not old:
        return {"is_initial": True}
    
    diff = {}
    old_basic, new_basic = old.get("basic", old), new.get("basic", new)
    old_org, new_org = old.get("organization", old), new.get("organization", new)
    old_hiring, new_hiring = old.get("hiring_focus", {}), new.get("hiring_focus", {})
    old_strategic, new_strategic = old.get("strategic_profile", {}), new.get("strategic_profile", {})
    
    if change := _value_change(old_org.get("employee_size", old.get("employees", "unknown")), new_org.get("employee_size", new.get("employees", "unknown"))):
        diff["employee_size_change"] = change
    
    added, removed = _set_diff(old_basic.get("industries"), new_basic.get("industries"))
    if added:
        diff["new_industries"] = added
    if removed:
        diff["dropped_industries"] = removed
    
    if country_change := _value_change(old_basic.get("country", old.get("country", "")), new_basic.get("country", new.get("country", ""))):
        diff["country_changed"] = country_change
    
    if hiring_diff := _hiring_changes(old_hiring, new_hiring):
        diff["hiring_focus_change"] = hiring_diff
    
    diff.update(_strategic_changes(old_strategic, new_strategic))
    return diff


MEANINGFUL_DIFF_KEYS = [
    "employee_size_change", "new_industries", "dropped_industries",
    "country_changed", "hiring_focus_change",
    "primary_markets_changed", "product_themes_changed", "target_segments_changed"
]
SIGNAL_BUCKETS = ("hiring", "product", "funding")

HIRING_FIELDS = ("engineering", "data", "product", "design", "marketing", "sales", "operations", "ai_ml_roles")
STRATEGIC_FIELDS = ("primary_markets", "product_themes", "target_segments")


def _value_change(old_value, new_value):
    return None if old_value in (None, "", "unknown") or old_value == new_value else {"old": old_value, "new": new_value}


def _set_diff(old_values, new_values):
    old_set, new_set = set(old_values or []), set(new_values or [])
    return list(new_set - old_set), list(old_set - new_set)


def _hiring_changes(old_hiring, new_hiring):
    changes = {k: {"old": old_hiring.get(k, 0), "new": new_hiring.get(k, 0), "change": new_hiring.get(k, 0) - old_hiring.get(k, 0)} 
               for k in HIRING_FIELDS if old_hiring.get(k, 0) != new_hiring.get(k, 0)}
    return changes or None


def _strategic_changes(old_strategic, new_strategic):
    changes = {}
    for field in STRATEGIC_FIELDS:
        old_set, new_set = set(old_strategic.get(field) or []), set(new_strategic.get(field) or [])
        added, removed = list(new_set - old_set), list(old_set - new_set)
        if added or removed:
            changes[f"{field}_changed"] = {"added": added, "removed": removed}
    return changes


def _create_signal(company: Company, competitor: Company, **fields) -> CompanySignal:
    """Create and stage a new competitor signal."""
    signal = CompanySignal()
    signal.company_id = company.id
    signal.competitor_id = competitor.id
    signal.is_new = True
    for key, value in fields.items():
        setattr(signal, key, value)
    db.session.add(signal)
    return signal


def _build_simple_payload(comp_name: str, diff_key: str, diff_value) -> Optional[dict]:
    """Unified payload builder for simple signals from diff changes."""
    if not diff_value:
        return None
    
    if diff_key == "employee_size_change":
        return {
            "signal_type": "headcount_change",
            "category": "hiring",
            "severity": "medium",
            "message": f"{comp_name} changed size from {diff_value['old']} to {diff_value['new']}",
            "details": "Employee size bracket changed, indicating organizational growth or contraction.",
        }
    
    if diff_key == "new_industries":
        return {
            "signal_type": "industry_shift",
            "category": "product",
            "severity": "medium",
            "message": f"{comp_name} expanding into new industries",
            "details": f"Added industries: {', '.join(diff_value)}",
        }
    
    if diff_key == "hiring_focus_change":
        growing = [k for k, v in diff_value.items() if v.get("change", 0) > 0]
        if not growing:
            return None
        return {
            "signal_type": "hiring_shift",
            "category": "hiring",
            "severity": "medium",
            "message": f"{comp_name} increasing focus on {', '.join(growing[:3])}",
            "details": "Hiring emphasis has shifted, suggesting strategic priorities.",
        }
    
    if diff_key == "primary_markets_changed":
        added = diff_value.get("added")
        if not added:
            return None
        return {
            "signal_type": "market_expansion",
            "category": "product",
            "severity": "high",
            "message": f"{comp_name} entering new markets: {', '.join(added[:3])}",
            "details": "Market expansion detected, potential competitive threat.",
        }
    
    return None


def _simple_signal_payloads(comp_name: str, diff: dict):
    """Generate simple signal payloads from diff changes."""
    for key in ["employee_size_change", "new_industries", "hiring_focus_change", "primary_markets_changed"]:
        payload = _build_simple_payload(comp_name, key, diff.get(key))
        if payload:
            yield payload


def _infer_category(signal_type: str) -> str:
    """Infer signal category from its type."""
    normalized = (signal_type or "").lower()
    if "hiring" in normalized or "headcount" in normalized:
        return "hiring"
    if "funding" in normalized:
        return "funding"
    return "product"


def _competitor_signal_query(company: Company):
    """Base query for competitor-only signals."""
    return None if not company else (
        CompanySignal.query.filter_by(company_id=company.id).filter(CompanySignal.competitor_id.isnot(None))
    )


def _iter_competitors(company: Company):
    """Yield competitor objects for a company."""
    return () if not company else (
        link.competitor for link in getattr(company, "competitors", []) if link and link.competitor
    )


def _unread_query(company: Company):
    query = _competitor_signal_query(company)
    return query.filter_by(is_new=True) if query else None


# =============================================================================
# Competitor Signal Generation
# =============================================================================

def generate_signals_for_competitor(company: Company, competitor: Company, diff: dict) -> list:
    """Generate AI signals from a competitor diff.
    
    IMPORTANT: All signals MUST have competitor_id set.
    """
    if diff.get("is_initial") or not diff or not any(k in diff for k in MEANINGFUL_DIFF_KEYS):
        return []
    
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

    data = chat_json(user_prompt=prompt, model="gpt-4o-mini", temperature=0.7, max_tokens=600, context=f"signals for {competitor.name}")
    if not data:
        return _generate_simple_competitor_signals(company, competitor, diff)
    
    signals = []
    for payload in data.get("signals", []):
        signal_type = payload.get("signal_type", "strategic_change")
        signals.append(_create_signal(company, competitor, signal_type=signal_type,
            category=payload.get("category") or _infer_category(signal_type),
            severity=payload.get("severity", "low"),
            message=payload.get("message", f"Change detected for {competitor.name}"),
            details=payload.get("details", ""), source_url=payload.get("source_url") or None))
    db.session.commit()
    return signals


def _generate_simple_competitor_signals(company: Company, competitor: Company, diff: dict) -> list:
    """Generate simple competitor signals without AI."""
    comp_name = competitor.name or "Competitor"
    signals = [_create_signal(company, competitor, **payload) for payload in _simple_signal_payloads(comp_name, diff)]
    db.session.commit()
    return signals


# =============================================================================
# Unread Signal Counting
# =============================================================================

def count_unread_signals(company: Company) -> int:
    """Count unread (new) competitor signals for a company."""
    query = _unread_query(company)
    return query.count() if query else 0


def count_unread_signals_by_category(company: Company) -> dict:
    """Count unread signals grouped by category.
    
    Returns dict with keys: 'hiring', 'product', 'funding', 'total'
    """
    counts = {bucket: 0 for bucket in SIGNAL_BUCKETS}
    query = _unread_query(company)
    if not query:
        counts["total"] = 0
        return counts
    signals = query.all()
    for sig in signals:
        counts[sig.category if sig.category in counts else "product"] += 1
    counts["total"] = len(signals)
    return counts


def mark_signals_as_read(company: Company) -> int:
    """Mark all competitor signals as read for a company. Returns count marked."""
    query = _unread_query(company)
    if not query:
        return 0
    count = query.update({"is_new": False})
    db.session.commit()
    return count


def get_competitor_signals(company: Company, category: Optional[str] = None) -> list:
    """Get all competitor signals for a company, optionally filtered by category.
    
    Args:
        company: The company whose signals to retrieve
        category: Optional filter by category ('hiring', 'product', 'funding')
    """
    query = _competitor_signal_query(company)
    if not query:
        return []
    if category:
        query = query.filter_by(category=category)
    return query.order_by(CompanySignal.created_at.desc()).all()


def group_signals_by_category(signals: list) -> dict:
    """Group signals into hiring/product/funding buckets."""
    groups = {bucket: [] for bucket in SIGNAL_BUCKETS}
    default_bucket = groups["product"]
    for sig in signals:
        (groups.get(sig.category) or default_bucket).append(sig)
    return groups


def get_all_competitor_snapshots(company: Company) -> dict:
    """Get the latest snapshot data for all competitors of a company.
    
    Returns a dict mapping competitor_id -> snapshot data dict
    """
    snapshots = {}
    for competitor in _iter_competitors(company):
        snap = load_last_competitor_snapshot(company, competitor)
        data = _snapshot_dict(snap)
        if data:
            snapshots[str(competitor.id)] = {
                "competitor_name": competitor.name,
                "data": data,
                "created_at": snap.created_at.isoformat() if snap and snap.created_at else None
            }
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
    
    for competitor in _iter_competitors(company):
        current = build_competitor_snapshot(company, competitor, force_ai=force_ai)
        old_data = _snapshot_dict(load_last_competitor_snapshot(company, competitor))
        diff = compute_diff(old_data, current)
        
        if diff.get("is_initial"):
            save_competitor_snapshot(company, competitor, current)
            continue
        
        if any(k in diff for k in MEANINGFUL_DIFF_KEYS):
            save_competitor_snapshot(company, competitor, current)
            generate_signals_for_competitor(company, competitor, diff)
    
    return get_competitor_signals(company)
