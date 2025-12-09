"""Main application routes - dashboard, company details, signals."""

import logging
import uuid

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from app import db
from models import CompanyCompetitor, User
from utils.auth import require_login
from utils.company_helpers import (
    enrich_company_if_needed,
    generate_landscape_if_needed,
    get_company_competitors,
    get_company_industries,
    refresh_competitors,
)
from services.signals import (
    count_unread_signals,
    count_unread_signals_by_category,
    get_all_competitor_snapshots,
    get_competitor_signals,
    group_signals_by_category,
    mark_signals_as_read,
)

main_bp = Blueprint("main", __name__)
SIGNAL_CATEGORIES = {"hiring", "product", "funding"}


def _require_company():
    company = getattr(g, "current_company", None)
    if company:
        return company
    flash("Company not found.", "error")
    return None


def _render_company_profile(target, is_competitor: bool):
    enrich_company_if_needed(target)
    generate_landscape_if_needed(target)
    db.session.commit()
    return render_template(
        "company_detail.html",
        company_obj=target,
        industries=get_company_industries(target),
        is_competitor=is_competitor,
    )


def _build_competitor_view_models(company):
    models = []
    for link in company.competitors:
        competitor = getattr(link, "competitor", None)
        if not competitor:
            continue
        if not competitor.number_of_employees and competitor.domain:
            try:
                enrich_company_if_needed(competitor, competitor.domain)
            except Exception:
                pass
        models.append({"company": competitor, "link": link})
    return models


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
    
    # Enrich main company data (including funding from OpenAI)
    try:
        enrich_company_if_needed(company)
        db.session.commit()
        db.session.refresh(company)
    except Exception as e:
        logging.error(f"Error enriching company: {e}", exc_info=True)
        db.session.rollback()
    
    # Fetch team members
    team_members = db.session.query(User).filter(
        User.company_id == company.id, User.is_active == True
    ).order_by(User.last_name.asc(), User.first_name.asc()).all()
    
    # Build competitor view models (enrich if needed)
    competitor_view_models = _build_competitor_view_models(company)
    
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    
    # Competitor signals, unread count, and snapshots
    all_signals = get_competitor_signals(company)
    signals_by_category = group_signals_by_category(all_signals)
    unread_count = count_unread_signals(company)
    unread_by_category = count_unread_signals_by_category(company)
    competitor_snapshots = get_all_competitor_snapshots(company)
    
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
        signals=all_signals,
        signals_by_category=signals_by_category,
        unread_count=unread_count,
        unread_by_category=unread_by_category,
        competitor_snapshots=competitor_snapshots,
    )


# =============================================================================
# Signals Page (marks signals as read)
# =============================================================================

@main_bp.route("/signals", methods=["GET"])
@require_login
def signals_page():
    """Display signals page and mark all signals as read."""
    company = _require_company()
    if not company:
        return redirect(url_for("main.homepage"))
    
    # Get category filter from query parameter
    category_filter = request.args.get("category", None)
    if category_filter not in SIGNAL_CATEGORIES:
        category_filter = None
    
    # Mark all signals as read
    mark_signals_as_read(company)
    
    # Get ALL signals once (for category counts in filter buttons)
    all_signals = get_competitor_signals(company)
    signals_by_category = group_signals_by_category(all_signals)
    
    signals = [s for s in all_signals if s.category == category_filter] if category_filter else all_signals
    
    return render_template(
        "signals.html",
        company=company,
        signals=signals,
        signals_by_category=signals_by_category,
        category_filter=category_filter,
    )


# =============================================================================
# Company Detail
# =============================================================================

@main_bp.route("/company", methods=["GET"])
@require_login
def company_detail():
    """Display detailed view of user's company."""
    company = _require_company()
    if not company:
        return redirect(url_for("main.homepage"))
    return _render_company_profile(company, False)


# =============================================================================
# Competitor Detail
# =============================================================================

@main_bp.route("/competitor/<competitor_id>", methods=["GET"])
@require_login
def competitor_detail(competitor_id):
    """Display detailed view of a competitor."""
    company = _require_company()
    if not company:
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
    
    return _render_company_profile(link.competitor, True)


# =============================================================================
# Refresh Competitor Signals
# =============================================================================

@main_bp.route("/refresh-signals", methods=["POST"])
@require_login
def refresh_signals():
    """Force refresh competitor signals."""
    company = _require_company()
    if not company:
        return redirect(url_for("main.homepage"))
    
    from services.signals import refresh_competitor_signals
    refresh_competitor_signals(company)
    
    flash("Competitor signals refreshed!", "success")
    return redirect(url_for("main.homepage") + "#signals")


@main_bp.route("/refresh-competitors", methods=["POST"])
@require_login
def refresh_competitors_route():
    """Refresh competitors using OpenAI (replaces old Company Enrich competitors)."""
    company = _require_company()
    if not company:
        return redirect(url_for("main.homepage"))
    
    try:
        refresh_competitors(company)
        db.session.commit()
        flash("Competitors refreshed with OpenAI data!", "success")
    except Exception as e:
        logging.error(f"Error refreshing competitors: {e}", exc_info=True)
        db.session.rollback()
        flash("Error refreshing competitors. Please try again.", "error")
    
    return redirect(url_for("main.homepage"))


# =============================================================================
# About Page
# =============================================================================

@main_bp.route("/about", methods=["GET"])
def about():
    """Display about page with founder information."""
    founders = [
        {"name": "Leo He", "role": "Co-founder", "image": url_for("static", filename="images/founders/6254D7A5-E3E1-4782-B39C-63BDC5D53FD4_1_105_c.jpeg"), "linkedin": "https://www.linkedin.com/in/leo-he-3582a1239/"},
        {"name": "Nathan Denys", "role": "Co-founder", "image": url_for("static", filename="images/founders/nathan-denys.jpg"), "linkedin": "https://www.linkedin.com/in/nathan-denys-a28618352/"},
        {"name": "Jean Knecht", "role": "Co-founder", "image": url_for("static", filename="images/founders/IMG_2696.JPG"), "linkedin": "https://www.linkedin.com/in/jean-knecht/"},
        {"name": "Niels Herreman", "role": "Co-founder", "image": url_for("static", filename="images/founders/niels-herreman.jpg"), "linkedin": "https://www.linkedin.com/in/niels-herreman-9955632a0/"},
        {"name": "Mattis Malfait", "role": "Co-founder", "image": url_for("static", filename="images/founders/mattis-malfait.jpg"), "linkedin": "https://www.linkedin.com/in/mattis-malfait-386280281/"},
        {"name": "Jeroen Vroman", "role": "Co-founder", "image": url_for("static", filename="images/founders/jeroen-vroman.jpg"), "linkedin": "https://www.linkedin.com/in/jeroenvroman/"},
    ]
    return render_template("about.html", founders=founders)


# =============================================================================
# Health Check
# =============================================================================

@main_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return "OK", 200