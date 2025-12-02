"""Main application routes - dashboard, company details, signals."""

import json
import uuid

from flask import Blueprint, flash, g, redirect, render_template, url_for

from app import db
from models import CompanyCompetitor, User
from utils.auth import require_login
from utils.company_helpers import (
    enrich_company_if_needed,
    generate_landscape_if_needed,
    get_company_competitors,
    get_company_industries,
)

main_bp = Blueprint("main", __name__)


# =============================================================================
# Homepage / Dashboard
# =============================================================================

@main_bp.route("/", methods=["GET"])
def homepage():
    """Display landing page for guests, main dashboard for logged-in users."""
    if not getattr(g, "current_user", None):
        return render_template("landing.html")
    
    company = g.current_company
    if not company:
        return render_template("index.html", company=None, users=[], metrics={})
    
    # Fetch team members
    team_members = (
        db.session.query(User)
        .filter(User.company_id == company.id, User.is_active == True)
        .order_by(User.last_name.asc(), User.first_name.asc())
        .all()
    )
    
    # Build competitor view models (enrich if needed)
    competitor_view_models = []
    for link in company.competitors:
        if link and link.competitor:
            comp = link.competitor
            if not comp.number_of_employees and comp.domain:
                try:
                    enrich_company_if_needed(comp, comp.domain)
                except Exception:
                    pass
            competitor_view_models.append({"company": comp, "link": link})
    
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    
    # Market positioning
    from services.market_positioning import generate_market_positioning
    mp = generate_market_positioning(company)
    
    # Signals and hiring intelligence
    from services.signals import (
        get_default_hiring_intelligence,
        load_last_snapshot,
        refresh_company_signals,
    )
    signals = refresh_company_signals(company)
    
    hiring_intel = None
    last_snap = load_last_snapshot(company)
    if last_snap:
        try:
            snap_data = json.loads(last_snap.data)
            hiring_intel = snap_data.get("hiring_intelligence")
        except Exception:
            pass
    
    if not hiring_intel:
        hiring_intel = get_default_hiring_intelligence()
    
    # Build metrics
    industries = get_company_industries(company)
    competitors = get_company_competitors(company)
    metrics = {
        "user_count": len(team_members),
        "competitor_count": len(competitors),
        "industry_count": len(industries),
        "total_funding": company.funding or 0,
    }
    
    return render_template(
        "index.html",
        company=company,
        users=team_members,
        industries=industries,
        metrics=metrics,
        competitor_view_models=competitor_view_models,
        mp=mp,
        signals=signals,
        hiring_intel=hiring_intel,
    )


# =============================================================================
# Company Detail
# =============================================================================

@main_bp.route("/company", methods=["GET"])
@require_login
def company_detail():
    """Display detailed view of user's company."""
    company = g.current_company
    if not company:
        flash("Company not found.", "error")
        return redirect(url_for("main.homepage"))
    
    enrich_company_if_needed(company)
    generate_landscape_if_needed(company)
    db.session.commit()
    
    return render_template(
        "company_detail.html",
        company_obj=company,
        industries=get_company_industries(company),
        is_competitor=False,
    )


# =============================================================================
# Competitor Detail
# =============================================================================

@main_bp.route("/competitor/<competitor_id>", methods=["GET"])
@require_login
def competitor_detail(competitor_id):
    """Display detailed view of a competitor."""
    company = g.current_company
    if not company:
        flash("Company not found.", "error")
        return redirect(url_for("main.homepage"))
    
    try:
        competitor_uuid = uuid.UUID(competitor_id)
    except (TypeError, ValueError):
        flash("Invalid competitor ID.", "error")
        return redirect(url_for("main.homepage"))
    
    link = (
        db.session.query(CompanyCompetitor)
        .filter(
            CompanyCompetitor.company_id == company.id,
            CompanyCompetitor.competitor_id == competitor_uuid,
        )
        .first()
    )
    
    if not link or not link.competitor:
        flash("Competitor not found.", "error")
        return redirect(url_for("main.homepage"))
    
    enrich_company_if_needed(link.competitor)
    generate_landscape_if_needed(link.competitor)
    db.session.commit()
    
    return render_template(
        "company_detail.html",
        company_obj=link.competitor,
        industries=get_company_industries(link.competitor),
        is_competitor=True,
    )


# =============================================================================
# Market Positioning
# =============================================================================

@main_bp.route("/market-positioning", methods=["GET"])
@require_login
def market_positioning():
    """Display market positioning analysis."""
    company = g.current_company
    if not company:
        flash("Company not found.", "error")
        return redirect(url_for("main.homepage"))
    
    from services.market_positioning import generate_market_positioning
    mp = generate_market_positioning(company)
    return render_template("market_positioning.html", company=company, mp=mp)


# =============================================================================
# Hiring Analysis Refresh
# =============================================================================

@main_bp.route("/refresh-analysis", methods=["POST"])
@require_login
def refresh_analysis():
    """Force refresh hiring analysis with new OpenAI call."""
    company = g.current_company
    if not company:
        flash("Company not found.", "error")
        return redirect(url_for("main.homepage"))
    
    from services.signals import force_refresh_analysis
    force_refresh_analysis(company)
    
    flash("Hiring analysis updated successfully!", "success")
    return redirect(url_for("main.homepage") + "#signals")


# =============================================================================
# About Page
# =============================================================================

@main_bp.route("/about", methods=["GET"])
def about():
    """Display about page with founder information."""
    founders = [
        {"name": "Leo He", "role": "Co-founder", "image": url_for("static", filename="images/founders/6254D7A5-E3E1-4782-B39C-63BDC5D53FD4_1_105_c.jpeg")},
        {"name": "Nathan Denys", "role": "Co-founder", "image": url_for("static", filename="images/founders/nathan-denys.jpg")},
        {"name": "Jean Knecht", "role": "Co-founder", "image": url_for("static", filename="images/founders/IMG_2696.JPG")},
        {"name": "Niels Herreman", "role": "Co-founder", "image": url_for("static", filename="images/founders/niels-herreman.jpg")},
        {"name": "Mattis Malfait", "role": "Co-founder", "image": url_for("static", filename="images/founders/mattis-malfait.jpg")},
        {"name": "Jeroen Vroman", "role": "Co-founder", "image": url_for("static", filename="images/founders/jeroen-vroman.jpg")},
    ]
    return render_template("about.html", founders=founders)


# =============================================================================
# Health Check
# =============================================================================

@main_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return "OK", 200
