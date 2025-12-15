"""Service voor competitor-signals en snapshots.

Belangrijk:
- signals worden ALLEEN gemaakt voor competitors, nooit voor het eigen bedrijf
- snapshots worden gebruikt om veranderingen over tijd te vergelijken
"""

import json
from copy import deepcopy
from datetime import datetime
from typing import Optional

from app import db
from models import Company, CompanySignal, CompanySnapshot
from services.openai_helpers import chat_json, responses_json_with_sources


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
    """Geef een lege, standaard snapshot-structuur terug."""
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
    """Zet een absoluut aantal werknemers om naar een grootte-bucket."""
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
    """Bouw een gestructureerde snapshot voor één competitor.

    - probeert eerst een bestaand snapshot te hergebruiken (cache)
    - gebruikt OpenAI om een rijk profiel te maken indien nodig
    - valt terug op een eenvoudig snapshot als AI niet werkt
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
    
    # Only use web search if force_ai is True (explicit refresh request)
    # This improves performance by using cached snapshots when possible
    ai_snapshot = _generate_ai_snapshot(company, competitor, industries, structured_data, use_web_search=force_ai)
    return ai_snapshot if ai_snapshot else _build_basic_snapshot(competitor, industries)


def _reuse_cached_snapshot(company: Company, competitor: Company, industries: list) -> Optional[dict]:
    """Probeer het laatste snapshot te hergebruiken voor snellere loads."""
    last_snap = load_last_competitor_snapshot(company, competitor)
    old_data = _snapshot_dict(last_snap)
    if not old_data or "basic" not in old_data or "strategic_profile" not in old_data:
        return None
    old_data["basic"]["industries"] = industries
    old_data["basic"]["country"] = competitor.country or ""
    org = old_data.setdefault("organization", {})
    org["employee_size"] = _get_employee_size_bucket(competitor.number_of_employees)
    return old_data


def _generate_ai_snapshot(company: Company, competitor: Company, industries: list, structured_data: dict, use_web_search: bool = False) -> Optional[dict]:
    """Generate AI-powered competitor snapshot, with optional web search.
    
    Args:
        company: Company tracking the competitor
        competitor: Competitor to profile
        industries: List of industry names
        structured_data: Basic company data
        use_web_search: If True, use web search (slower but more current). Default False for performance.
    """
    # Only use web search if explicitly requested (for performance)
    if use_web_search:
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

        # Use Responses API with web search to get both data and sources
        web_result_data = responses_json_with_sources(
            web_prompt,
            tools=[{"type": "web_search"}],
            tool_choice="auto",
            context=f"web search snapshot for {competitor.name}"
        )
        if web_result_data and web_result_data.get("data"):
            # Sources are available but not stored in snapshot (snapshot is for comparison)
            # Sources will be used later when generating signals
            return _validate_snapshot(web_result_data["data"])

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
SIGNAL_BUCKETS = ("hiring", "product", "funding")  # alle mogelijke signal-categorieën

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
    """Create and stage a new competitor signal.
    
    Handles related_news by storing it as JSON in details field.
    If related_news is provided, it's stored alongside the details text.
    """
    signal = CompanySignal()
    signal.company_id = company.id
    signal.competitor_id = competitor.id
    signal.is_new = True
    
    # Extract related_news if present (will be stored in details as JSON)
    related_news = fields.pop("related_news", None)
    details_text = fields.pop("details", "")
    
    # Store related_news in details as JSON if present
    if related_news:
        details_obj = {"text": details_text, "related_news": related_news}
        signal.details = json.dumps(details_obj)
    else:
        signal.details = details_text
    
    # Set other fields
    for key, value in fields.items():
        setattr(signal, key, value)
    
    db.session.add(signal)
    return signal


def parse_signal_details(signal: CompanySignal) -> dict:
    """Parse signal details field to extract text and related_news.
    
    Returns:
        {
            "text": str,  # The details text
            "related_news": list  # List of related news items, or empty list
        }
    """
    if not signal or not signal.details:
        return {"text": "", "related_news": []}
    
    try:
        # Try to parse as JSON (new format with related_news)
        parsed = json.loads(signal.details)
        if isinstance(parsed, dict) and "related_news" in parsed:
            return {
                "text": parsed.get("text", ""),
                "related_news": parsed.get("related_news", [])
            }
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Fallback: treat as plain text (old format)
    return {"text": signal.details, "related_news": []}


def collect_all_related_news(signals: list) -> list:
    """Collect all related_news from a list of signals, with signal context.
    
    Returns:
        List of dicts with structure:
        {
            "title": str,
            "url": str,
            "summary": str,
            "source_name": str,
            "signal": CompanySignal,  # Reference to the signal
            "competitor": Company,  # Reference to the competitor
            "signal_message": str,  # The signal message
            "signal_category": str,  # The signal category
            "created_at": datetime  # When the signal was created
        }
    """
    all_news = []
    seen_urls = set()  # Deduplicate by URL
    
    for signal in signals:
        details_data = parse_signal_details(signal)
        for news_item in details_data.get("related_news", []):
            url = news_item.get("url", "")
            # Skip if URL is empty or already seen (deduplication)
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            
            news_with_context = {
                "title": news_item.get("title", "") or url,  # Use URL as title if title is empty
                "url": url,
                "summary": news_item.get("summary", ""),
                "source_name": news_item.get("source_name", ""),
                "signal": signal,
                "competitor": signal.competitor if hasattr(signal, "competitor") else None,
                "signal_message": signal.message or "",
                "signal_category": signal.category or "",
                "created_at": signal.created_at,
            }
            all_news.append(news_with_context)
    
    # Sort by created_at (most recent first)
    all_news.sort(key=lambda x: x["created_at"] if x["created_at"] else datetime.min, reverse=True)
    return all_news


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


def _force_category_from_signal_type(signal_type: str) -> str:
    """Forceer de juiste categorie op basis van signal_type.

    Beschermlaag tegen onbetrouwbare AI-output: zelfs als de AI een
    andere category voorstelt, gebruiken we hier altijd een vaste mapping.
    """
    if not signal_type:
        return "product"
    
    normalized = (signal_type or "").lower()
    
    # STRICT mapping - these signal types MUST map to these categories
    if normalized in ("headcount_change", "hiring_shift"):
        return "hiring"
    
    if normalized in ("funding_round", "funding_change"):
        return "funding"
    
    # All other signal types default to product
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

def _derive_change_description(competitor: Company, diff: dict) -> str:
    """Derive a compact change description from diff for web search queries."""
    changes = []
    
    if size_change := diff.get("employee_size_change"):
        old_size = size_change.get("old", "unknown")
        new_size = size_change.get("new", "unknown")
        changes.append(f"headcount changed from {old_size} to {new_size} employees")
    
    if new_industries := diff.get("new_industries"):
        changes.append(f"entered new industries: {', '.join(new_industries[:3])}")
    
    if dropped_industries := diff.get("dropped_industries"):
        changes.append(f"exited industries: {', '.join(dropped_industries[:3])}")
    
    if hiring_diff := diff.get("hiring_focus_change"):
        increased = [k for k, v in hiring_diff.items() if v.get("change", 0) > 0]
        if increased:
            changes.append(f"increased hiring focus in: {', '.join(increased[:3])}")
    
    if funding_change := diff.get("funding_change"):
        old_funding = funding_change.get("old", "unknown")
        new_funding = funding_change.get("new", "unknown")
        changes.append(f"funding changed from {old_funding} to {new_funding}")
    
    if market_change := diff.get("primary_markets_changed"):
        added = market_change.get("added", [])
        if added:
            changes.append(f"expanded to new markets: {', '.join(added[:2])}")
    
    if not changes:
        return f"{competitor.name} organizational changes"
    
    return f"{competitor.name}: {', '.join(changes[:3])}"


def generate_signals_for_competitor(company: Company, competitor: Company, diff: dict, use_web_search: bool = True) -> list:
    """Genereer AI-signals voor één competitor op basis van een diff.

    - gebruikt web search (Responses API) om, indien ingeschakeld, rijke signals met nieuws te bouwen
    - valt anders terug op eenvoudige, niet-AI gebaseerde signals
    - alle gegenereerde signals krijgen altijd een geldige `competitor_id`
    """
    if diff.get("is_initial") or not diff or not any(k in diff for k in MEANINGFUL_DIFF_KEYS):
        return []
    
    # Korte samenvatting maken van de changes voor gebruik in de prompt
    change_desc = _derive_change_description(competitor, diff)
    
    # Prompt die de structuur van de gewenste signals uitlegt (fallback zonder web search)
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
- Change description: {change_desc}
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
      "source_url": "Optional URL to news article, company page, or other source (leave empty if not available)",
      "related_news": []
    }}
  ]
}}

CRITICAL CATEGORY RULES (MUST FOLLOW):
- "hiring": MUST use for:
  * headcount_change (employee size changes)
  * hiring_shift (hiring focus changes)
  * Any signal about team growth, new hires, job postings, recruitment
- "funding": MUST use for:
  * funding_round (any funding changes)
  * Any signal about investments, investors, capital raises, funding announcements
- "product": MUST use for:
  * product_launch (new products)
  * market_expansion (entering new markets)
  * industry_shift (industry changes)
  * Other strategic/product changes

Signal Type → Category MAPPING (STRICT):
- headcount_change → category: "hiring" (REQUIRED)
- hiring_shift → category: "hiring" (REQUIRED)
- funding_round → category: "funding" (REQUIRED)
- product_launch → category: "product" (REQUIRED)
- market_expansion → category: "product" (REQUIRED)
- industry_shift → category: "product" (REQUIRED)
- strategic_change → infer from context, but prefer "product" if unclear

Rules:
- Focus on what this means COMPETITIVELY for the user watching this competitor.
- Severity should reflect potential competitive impact.
- Be specific about the competitor name in messages.
- ALWAYS assign the CORRECT category based on signal_type mapping above.
- DO NOT default to "product" - use "hiring" for headcount/hiring changes, "funding" for funding changes.
- Return empty signals array if changes are trivial.
- Include empty related_news array (web search not available in this fallback)."""

    # Try Responses API with web search first to get sources and related news
    web_prompt = f"""You are an analyst for a competitive intelligence tool.
You receive a "diff" describing changes in a COMPETITOR's organizational state.

Your task:
- Search the web for recent news, articles, or information about {competitor.name} related to these changes: {change_desc}
- Interpret the diff in context of real-world events
- Decide which changes are meaningful for competitive analysis
- Categorize each signal into one of three categories: hiring, product, or funding
- For each signal, find and include related news articles from your web search results
- Return them as an array of structured "signals" with related_news

INPUT:
- Your company is tracking this competitor: {competitor.name}
- Competitor description: {competitor.headline or 'N/A'}
- Change description: {change_desc}
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
      "source_url": "Primary URL to news article, company page, or other source (leave empty if not available)",
      "related_news": [
        {{
          "title": "Article title from web search",
          "url": "Full URL to the article",
          "summary": "1-2 sentence summary of the article",
          "source_name": "Name of the publication/source (e.g., 'TechCrunch', 'Company Blog')"
        }}
      ]
    }}
  ]
}}

CRITICAL CATEGORY RULES (MUST FOLLOW):
- "hiring": MUST use for:
  * headcount_change (employee size changes)
  * hiring_shift (hiring focus changes)
  * Any signal about team growth, new hires, job postings, recruitment
- "funding": MUST use for:
  * funding_round (any funding changes)
  * Any signal about investments, investors, capital raises, funding announcements
- "product": MUST use for:
  * product_launch (new products)
  * market_expansion (entering new markets)
  * industry_shift (industry changes)
  * Other strategic/product changes

Signal Type → Category MAPPING (STRICT):
- headcount_change → category: "hiring" (REQUIRED)
- hiring_shift → category: "hiring" (REQUIRED)
- funding_round → category: "funding" (REQUIRED)
- product_launch → category: "product" (REQUIRED)
- market_expansion → category: "product" (REQUIRED)
- industry_shift → category: "product" (REQUIRED)
- strategic_change → infer from context, but prefer "product" if unclear

Rules:
- Focus on what this means COMPETITIVELY for the user watching this competitor.
- Severity should reflect potential competitive impact.
- Be specific about the competitor name in messages.
- ALWAYS assign the CORRECT category based on signal_type mapping above.
- DO NOT default to "product" - use "hiring" for headcount/hiring changes, "funding" for funding changes.
- Return empty signals array if changes are trivial.
- Use web search to find recent news/articles (last 3-6 months) about these changes.
- Include 1-3 related_news entries per signal when relevant articles are found.
- Extract title, URL, summary, and source_name from web search results.
- If no relevant news found, return empty related_news array."""

    data = None
    sources = []
    
    # Gebruik enkel web search voor AI-signals; geen fallback naar andere AI-calls.
    if use_web_search:
        web_result = responses_json_with_sources(
            web_prompt,
            tools=[{"type": "web_search"}],
            tool_choice="auto",
            context=f"web search signals for {competitor.name}",
        )
        if web_result:
            data = web_result.get("data")
            sources = web_result.get("sources", [])
    
    # Als web search geen bruikbare data oplevert (of uitgeschakeld is),
    # val terug op de eenvoudige, niet-AI gebaseerde signal-logica.
    if not data:
        return _generate_simple_competitor_signals(company, competitor, diff)
    
    signals = []
    for payload in data.get("signals", []):
        signal_type = payload.get("signal_type", "strategic_change")
        
        # Extract related_news from payload
        related_news = payload.get("related_news", [])
        # If no related_news in payload but we have sources, create basic entries with URL as title
        if not related_news and sources:
            related_news = [{"url": url, "title": url, "summary": "", "source_name": ""} for url in sources[:3]]
        
        # Use source_url from payload, or first source from web search if available
        source_url = payload.get("source_url")
        if not source_url and sources:
            source_url = sources[0]  # Use first source from web search
        
        # FORCE correct category based on signal_type (ignore AI if wrong)
        # This ensures signals are always correctly categorized
        category = _force_category_from_signal_type(signal_type)
        
        signals.append(_create_signal(company, competitor, signal_type=signal_type,
            category=category,
            severity=payload.get("severity", "low"),
            message=payload.get("message", f"Change detected for {competitor.name}"),
            details=payload.get("details", ""), source_url=source_url,
            related_news=related_news if related_news else None))
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
        category = (sig.category or "").strip().lower() if sig.category else "product"
        # Normalize category to match buckets
        if category not in groups:
            category = "product"
        groups[category].append(sig)
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
