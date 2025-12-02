"""Signals service - detects company changes and generates AI-powered alerts."""

import json
import os
from datetime import datetime
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
# Hiring Intelligence
# =============================================================================

def get_default_hiring_intelligence() -> dict:
    """Return default hiring intelligence structure."""
    return {
        "hiring_summary": "Hiring analysis not available.",
        "current_focus": {
            "engineering": 0, "data": 0, "product": 0, "design": 0,
            "marketing": 0, "operations": 0, "sales": 0,
            "ai_ml_roles": 0, "senior_leadership": 0
        },
        "department_signals": {
            "growing_departments": [],
            "shrinking_departments": [],
            "emerging_skills": [],
            "strategic_role_clusters": []
        },
        "strategic_interpretation": {
            "growth_stage": "Unknown",
            "likely_hiring_priorities": [],
            "talent_risks": [],
            "org_pivots": []
        }
    }


def extract_hiring_intelligence(company: Company, industries: list, competitors: list) -> dict:
    """Extract comprehensive hiring intelligence using OpenAI."""
    default = get_default_hiring_intelligence()
    if not company:
        return default
    
    client = _get_openai_client()
    if not client:
        return default
    
    prompt = f"""You are an expert in organizational analysis, hiring intelligence, and workforce pattern detection. Your task is to analyze a company based only on the provided structured data and output a detailed hiring-focused intelligence profile.

Analyze:
- company description
- industries
- employee count or growth indicators
- competitor landscape
- known markets and products
- any inferred organizational strategy
- typical hiring patterns for companies in similar sectors

Your output MUST be valid JSON with the exact structure below.
Do NOT include commentary, markdown, or any text outside JSON.

{{
  "hiring_summary": "",
  "current_focus": {{
    "engineering": 0,
    "data": 0,
    "product": 0,
    "design": 0,
    "marketing": 0,
    "operations": 0,
    "sales": 0,
    "ai_ml_roles": 0,
    "senior_leadership": 0
  }},
  "department_signals": {{
    "growing_departments": [],
    "shrinking_departments": [],
    "emerging_skills": [],
    "strategic_role_clusters": []
  }},
  "strategic_interpretation": {{
    "growth_stage": "",
    "likely_hiring_priorities": [],
    "talent_risks": [],
    "org_pivots": []
  }}
}}

Definitions:
- All numeric fields (0–5) indicate strength of hiring signals.
- Lists should contain 1–5 short items each.
- Summaries must be analytical, factual, and based on the input.
- Only use information explicitly inferable from the input.
- If uncertain about any field, make the best high-level inference.
- NEVER output null, None, or missing keys. Always fill them.
- Use concise but insightful language.

Input Data:
Company name: {company.name}
Description: {company.headline or 'N/A'}
Industries: {', '.join(industries) if industries else 'N/A'}
Employee Count: {company.number_of_employees or 'Unknown'}
Competitors: {', '.join(competitors) if competitors else 'N/A'}"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=800
        )
        content = _clean_json_response(
            resp.choices[0].message.content if resp.choices else ""
        )
        data = json.loads(content)
        
        # Validate current_focus scores (0-5)
        if "current_focus" in data:
            for key in default["current_focus"]:
                val = data["current_focus"].get(key, 0)
                data["current_focus"][key] = max(0, min(5, int(val))) if isinstance(val, (int, float)) else 0
        else:
            data["current_focus"] = default["current_focus"]
        
        # Ensure all required top-level keys exist
        for key in default:
            if key not in data:
                data[key] = default[key]
        
        # Ensure department_signals has all keys
        for key in default["department_signals"]:
            if key not in data.get("department_signals", {}):
                data.setdefault("department_signals", {})[key] = []
        
        # Ensure strategic_interpretation has all keys
        for key in default["strategic_interpretation"]:
            if key not in data.get("strategic_interpretation", {}):
                default_val = "Unknown" if key == "growth_stage" else []
                data.setdefault("strategic_interpretation", {})[key] = default_val
        
        return data
    except Exception:
        return default


def extract_role_keywords(company: Company, industries: list, competitors: list) -> dict:
    """Legacy function - extracts just role keywords from full hiring intelligence."""
    intel = extract_hiring_intelligence(company, industries, competitors)
    return intel.get("current_focus", get_default_hiring_intelligence()["current_focus"])


# =============================================================================
# Snapshot Management
# =============================================================================

def build_org_snapshot(company: Company, force_refresh_keywords: bool = False) -> dict:
    """Build a snapshot of company's current organizational state.
    
    Args:
        company: The company to build snapshot for
        force_refresh_keywords: If True, calls OpenAI for new hiring_intelligence.
                               If False, reuses existing data from last snapshot.
    """
    if not company:
        return {}
    
    # Gather industries
    industries = sorted([
        link.industry.name
        for link in company.industries
        if link.industry and link.industry.name
    ])
    
    # Gather competitors
    competitors = sorted([
        comp.name or comp.domain or "Unknown"
        for link in company.competitors
        if link.competitor
        for comp in [link.competitor]
    ])
    
    # Get hiring intelligence (reuse or generate new)
    hiring_intelligence = None
    if not force_refresh_keywords:
        last_snap = load_last_snapshot(company)
        if last_snap:
            try:
                old_data = json.loads(last_snap.data)
                hiring_intelligence = old_data.get("hiring_intelligence")
            except Exception:
                pass
    
    if not hiring_intelligence:
        hiring_intelligence = extract_hiring_intelligence(company, industries, competitors)
    
    return {
        "employees": company.number_of_employees or 0,
        "industries": industries,
        "competitors": competitors,
        "description": (company.headline or "")[:500],
        "country": company.country or "",
        "funding": company.funding or 0,
        "hiring_intelligence": hiring_intelligence,
        "role_keywords": hiring_intelligence.get("current_focus", {}),  # Legacy
    }


def load_last_snapshot(company: Company) -> Optional[CompanySnapshot]:
    """Load the most recent snapshot for a company."""
    if not company:
        return None
    return (
        CompanySnapshot.query
        .filter_by(company_id=company.id)
        .order_by(CompanySnapshot.created_at.desc())
        .first()
    )


def save_snapshot(company: Company, snapshot: dict) -> CompanySnapshot:
    """Save a new snapshot for a company."""
    snap = CompanySnapshot(company_id=company.id, data=json.dumps(snapshot))
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
    
    # Employee count change
    old_emp = old.get("employees", 0) or 0
    new_emp = new.get("employees", 0) or 0
    if old_emp != new_emp and old_emp > 0:
        change_pct = ((new_emp - old_emp) / old_emp) * 100
        diff["employee_count_change"] = {
            "old": old_emp,
            "new": new_emp,
            "change_percent": round(change_pct, 1)
        }
    
    # Industry changes
    old_ind, new_ind = set(old.get("industries", [])), set(new.get("industries", []))
    if old_ind != new_ind:
        if new_ind - old_ind:
            diff["new_industries"] = list(new_ind - old_ind)
        if old_ind - new_ind:
            diff["dropped_industries"] = list(old_ind - new_ind)
    
    # Competitor changes
    old_comp, new_comp = set(old.get("competitors", [])), set(new.get("competitors", []))
    if old_comp != new_comp:
        if new_comp - old_comp:
            diff["new_competitors"] = list(new_comp - old_comp)
        if old_comp - new_comp:
            diff["dropped_competitors"] = list(old_comp - new_comp)
    
    # Country change
    if old.get("country") and old.get("country") != new.get("country"):
        diff["country_changed"] = {"old": old.get("country"), "new": new.get("country")}
    
    # Funding change
    old_fund, new_fund = old.get("funding", 0) or 0, new.get("funding", 0) or 0
    if old_fund != new_fund and old_fund > 0:
        diff["funding_change"] = {"old": old_fund, "new": new_fund}
    
    # Description change (significant)
    old_desc, new_desc = old.get("description", ""), new.get("description", "")
    if old_desc and new_desc and len(old_desc) > 50:
        if abs(len(old_desc) - len(new_desc)) > 100 or old_desc[:100] != new_desc[:100]:
            diff["description_changed"] = True
    
    # Role keywords diff
    old_kw, new_kw = old.get("role_keywords", {}), new.get("role_keywords", {})
    if old_kw and new_kw:
        role_diff = {}
        for key in ["engineering", "data", "product", "design", "marketing", "operations", "sales"]:
            old_val, new_val = old_kw.get(key, 0), new_kw.get(key, 0)
            if old_val != new_val:
                role_diff[key] = new_val - old_val
        
        if role_diff:
            diff["role_keywords_diff"] = role_diff
            diff["hiring_trend"] = {
                "positive_roles": [k for k, v in role_diff.items() if v >= 2],
                "negative_roles": [k for k, v in role_diff.items() if v <= -2],
                "net_growth": sum(role_diff.values())
            }
    
    return diff


# =============================================================================
# Signal Generation
# =============================================================================

MEANINGFUL_DIFF_KEYS = [
    "employee_count_change", "new_industries", "dropped_industries",
    "new_competitors", "dropped_competitors", "country_changed",
    "funding_change", "description_changed", "role_keywords_diff", "hiring_trend"
]


def generate_signals_from_diff(company: Company, diff: dict) -> list:
    """Generate AI signals from a diff."""
    if diff.get("is_initial") or not diff:
        return []
    
    if not any(k in diff for k in MEANINGFUL_DIFF_KEYS):
        return []
    
    client = _get_openai_client()
    if not client:
        return _generate_simple_signals(company, diff)
    
    prompt = f"""You are an analyst for a competitive intelligence tool.
You receive a "diff" describing changes in a company's organizational and competitive context.

Your task:
- Interpret the diff
- Decide which changes are meaningful for competitive analysis
- Return them as an array of structured "signals"

INPUT:
- Company name: {company.name}
- Diff (JSON): {json.dumps(diff)}

OUTPUT FORMAT (MUST BE VALID JSON, NO MARKDOWN):

{{
  "signals": [
    {{
      "signal_type": "headcount_change" | "industry_shift" | "competitor_set_change" | "org_shift" | "funding_change" | "hiring_trend" | "technical_focus" | "department_growth" | "role_shift",
      "severity": "low" | "medium" | "high",
      "message": "Short UI-ready title (~1 sentence)",
      "details": "2-4 sentence explanation of why this matters competitively."
    }}
  ]
}}

Signal type guidelines:
- headcount_change: overall employee count changes
- industry_shift: new or dropped industries
- competitor_set_change: new or dropped competitors
- org_shift: general organizational changes
- funding_change: funding amount changes
- hiring_trend: overall hiring direction (growth/decline)
- technical_focus: emphasis on engineering/data roles
- department_growth: specific department expansion
- role_shift: change in role priorities

Rules:
- Only include signals if there is something meaningful in the diff.
- Severity should reflect potential competitive impact.
- Be specific, avoid vague business jargon.
- Return empty signals array if changes are trivial.
- For role_keywords_diff and hiring_trend, generate hiring-related signals."""

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
        
        # Clear old signals and create new ones
        CompanySignal.query.filter_by(company_id=company.id).delete()
        
        signals = []
        for s in signals_data:
            sig = CompanySignal(
                company_id=company.id,
                signal_type=s.get("signal_type", "org_shift"),
                severity=s.get("severity", "low"),
                message=s.get("message", "Change detected"),
                details=s.get("details", "")
            )
            db.session.add(sig)
            signals.append(sig)
        
        db.session.commit()
        return signals
    except Exception:
        return _generate_simple_signals(company, diff)


def _generate_simple_signals(company: Company, diff: dict) -> list:
    """Generate simple signals without AI when OpenAI is unavailable."""
    CompanySignal.query.filter_by(company_id=company.id).delete()
    signals = []
    
    # Headcount change
    if "employee_count_change" in diff:
        change = diff["employee_count_change"]
        pct = change.get("change_percent", 0)
        severity = "high" if abs(pct) > 20 else "medium" if abs(pct) > 10 else "low"
        direction = "increased" if pct > 0 else "decreased"
        sig = CompanySignal(
            company_id=company.id,
            signal_type="headcount_change",
            severity=severity,
            message=f"Headcount has {direction} by {abs(pct):.0f}%",
            details=f"Employee count changed from {change['old']:,} to {change['new']:,}."
        )
        db.session.add(sig)
        signals.append(sig)
    
    # New industries
    if "new_industries" in diff:
        sig = CompanySignal(
            company_id=company.id,
            signal_type="industry_shift",
            severity="medium",
            message="New industries associated with company",
            details=f"Added industries: {', '.join(diff['new_industries'])}"
        )
        db.session.add(sig)
        signals.append(sig)
    
    # New competitors
    if "new_competitors" in diff:
        sig = CompanySignal(
            company_id=company.id,
            signal_type="competitor_set_change",
            severity="medium",
            message="Competitor set has changed",
            details=f"New competitors identified: {', '.join(diff['new_competitors'])}"
        )
        db.session.add(sig)
        signals.append(sig)
    
    # Funding change
    if "funding_change" in diff:
        change = diff["funding_change"]
        sig = CompanySignal(
            company_id=company.id,
            signal_type="funding_change",
            severity="high",
            message="Funding amount has changed",
            details=f"Funding changed from €{change['old']:,} to €{change['new']:,}."
        )
        db.session.add(sig)
        signals.append(sig)
    
    # Hiring trend
    if "hiring_trend" in diff:
        trend = diff["hiring_trend"]
        positive, negative = trend.get("positive_roles", []), trend.get("negative_roles", [])
        
        if positive:
            sig = CompanySignal(
                company_id=company.id,
                signal_type="hiring_trend",
                severity="medium" if len(positive) > 1 else "low",
                message=f"Increased hiring focus: {', '.join(positive)}",
                details=f"Role emphasis has increased for {', '.join(positive)} departments."
            )
            db.session.add(sig)
            signals.append(sig)
        
        if negative:
            sig = CompanySignal(
                company_id=company.id,
                signal_type="role_shift",
                severity="medium" if len(negative) > 1 else "low",
                message=f"Reduced hiring focus: {', '.join(negative)}",
                details=f"Role emphasis has decreased for {', '.join(negative)} departments."
            )
            db.session.add(sig)
            signals.append(sig)
    
    # Technical focus
    if "role_keywords_diff" in diff:
        role_diff = diff["role_keywords_diff"]
        tech_growth = sum(role_diff.get(r, 0) for r in ["engineering", "data", "product"])
        
        if tech_growth >= 3:
            sig = CompanySignal(
                company_id=company.id,
                signal_type="technical_focus",
                severity="high" if tech_growth >= 5 else "medium",
                message="Strong growth in technical roles",
                details="Increased emphasis on engineering, data, and product roles."
            )
            db.session.add(sig)
            signals.append(sig)
    
    db.session.commit()
    return signals


# =============================================================================
# Main Orchestrators
# =============================================================================

def refresh_company_signals(company: Company) -> list:
    """Main orchestrator: refresh signals for a company (no OpenAI call for role_keywords)."""
    if not company:
        return []
    
    # Build current snapshot (reuses existing role_keywords)
    current = build_org_snapshot(company, force_refresh_keywords=False)
    
    # Load last snapshot
    last_snap = load_last_snapshot(company)
    old_data = json.loads(last_snap.data) if last_snap else None
    
    # Compute diff
    diff = compute_diff(old_data, current)
    
    # Initial snapshot: generate role_keywords, save, return empty
    if diff.get("is_initial"):
        current = build_org_snapshot(company, force_refresh_keywords=True)
        save_snapshot(company, current)
        return []
    
    # No meaningful changes: return existing signals
    if not any(k in diff for k in MEANINGFUL_DIFF_KEYS):
        return list(
            CompanySignal.query
            .filter_by(company_id=company.id)
            .order_by(CompanySignal.created_at.desc())
            .all()
        )
    
    # Save new snapshot and generate signals
    save_snapshot(company, current)
    return generate_signals_from_diff(company, diff)


def force_refresh_analysis(company: Company) -> tuple:
    """Force refresh hiring analysis with new OpenAI call.
    
    Returns:
        tuple: (role_keywords dict, signals list)
    """
    if not company:
        return {}, []
    
    # Build new snapshot with fresh role_keywords
    current = build_org_snapshot(company, force_refresh_keywords=True)
    
    # Load last snapshot for comparison
    last_snap = load_last_snapshot(company)
    old_data = json.loads(last_snap.data) if last_snap else None
    
    # Compute diff and save
    diff = compute_diff(old_data, current)
    save_snapshot(company, current)
    
    # Generate signals if meaningful changes
    signals = []
    if not diff.get("is_initial") and diff:
        signals = generate_signals_from_diff(company, diff)
    
    return current.get("role_keywords", {}), signals
