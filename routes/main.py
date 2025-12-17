"""Hoofd-routes van de applicatie: dashboard, company details en signals.

Deze file toont duidelijk:
- welke data uit de database wordt gelezen
- wanneer er wijzigingen gebeuren (alleen in POST-routes)
- dat GET-routes geen externe API-calls doen
"""

import logging
import uuid

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from app import db
from models import CompanyCompetitor, User
from utils.auth import require_login
from utils.company_helpers import get_company_competitors, get_company_industries, refresh_competitors
from services.signals import (
    collect_all_related_news,
    count_unread_signals,
    count_unread_signals_by_category,
    get_all_competitor_snapshots,
    get_competitor_signals,
    group_signals_by_category,
    mark_signals_as_read,
)

main_bp = Blueprint("main", __name__)


def _require_company():
    """Zorg ervoor dat er een huidige company beschikbaar is.

    Als de ingelogde gebruiker geen gekoppelde company heeft,
    tonen we een foutmelding en gaan we terug naar het dashboard.
    """
    company = getattr(g, "current_company", None)
    if company:
        return company
    flash("Company not found.", "error")
    return None


def _render_company_profile(target, is_competitor: bool):
    """Toon het detailprofiel van een company of competitor.

    Belangrijk:
    - deze functie leest alleen uit de database
    - er worden hier geen externe API-calls meer gedaan
    - alle enrichment gebeurt bij signup of via expliciete POST-acties
    """
    return render_template(
        "company_detail.html",
        company_obj=target,
        industries=get_company_industries(target),
        is_competitor=is_competitor,
    )


def _build_competitor_view_models(company):
    """Bouw een eenvoudige lijst van competitors voor het dashboard.

    We maken hier een vlakke lijst van dicts zodat de template eenvoudig
    te begrijpen is voor een beginnende ontwikkelaar.
    """
    models = []
    for link in company.competitors:
        competitor = getattr(link, "competitor", None)
        if not competitor:
            continue
        models.append({"company": competitor, "link": link})
    return models


# =============================================================================
# Homepage / Dashboard
# =============================================================================

@main_bp.route("/", methods=["GET"])
def homepage():
    """Toon ofwel de marketing landing page, ofwel het hoofd-dashboard.

    - Gast (niet ingelogd) → eenvoudige landingpagina
    - Ingelogde gebruiker  → dashboard met:
        * teamleden
        * competitors
        * signals en unread counts
        * snapshots en recent nieuws
    LET OP: deze GET-route leest alleen uit de database en doet geen externe API-calls.
    """
    if not getattr(g, "current_user", None):
        return render_template("landing.html")
    
    company = g.current_company
    if not company:
        return render_template("index.html", company=None, users=[], metrics={})
    
    # 1. Haal alle actieve teamleden op voor deze company.
    team_members = db.session.query(User).filter(
        User.company_id == company.id, User.is_active == True
    ).order_by(User.last_name.asc(), User.first_name.asc()).all()
    
    # 2. Bouw eenvoudige view models voor competitors op basis van bestaande data.
    competitor_view_models = _build_competitor_view_models(company)
    
    # 3. Haal alle signals, unread counts en snapshots op uit de database.
    all_signals = get_competitor_signals(company)
    signals_by_category = group_signals_by_category(all_signals)
    unread_count = count_unread_signals(company)
    unread_by_category = count_unread_signals_by_category(company)
    competitor_snapshots = get_all_competitor_snapshots(company)
    all_related_news = collect_all_related_news(all_signals)
    
    # 4. Bouw een klein metrics-overzicht voor in het dashboard.
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
        all_related_news=all_related_news,
    )


# =============================================================================
# Signals Page (marks signals as read)
# =============================================================================

@main_bp.route("/signals", methods=["GET"])
@require_login
def signals_page():
    """Toon de signals pagina en markeer alle signals als gelezen.

    Deze route:
    - leest alle signals uit de database
    - groepeert ze per category
    - markeert alles als gelezen
    - haalt alle related news op voor de "Recent News" tab
    """
    company = _require_company()
    if not company:
        return redirect(url_for("main.homepage"))
    
    # Get category filter from query parameter
    category_filter = request.args.get("category", None)
    if category_filter not in ("hiring", "product", "funding"):
        category_filter = None
    
    # Mark all signals as read
    mark_signals_as_read(company)
    
    # Get ALL signals once (for category counts in filter buttons)
    all_signals = get_competitor_signals(company)
    signals_by_category = group_signals_by_category(all_signals)
    
    # Check if user wants to see news tab
    view_mode = request.args.get("view", "signals")  # "signals" or "news"
    
    signals = [s for s in all_signals if s.category == category_filter] if category_filter else all_signals
    
    # Collect all related news (always collect, but only show in news view)
    all_related_news = collect_all_related_news(all_signals)
    
    return render_template(
        "signals.html",
        company=company,
        signals=signals,
        signals_by_category=signals_by_category,
        category_filter=category_filter,
        view_mode=view_mode,
        all_related_news=all_related_news,
    )


# =============================================================================
# Company Detail
# =============================================================================

@main_bp.route("/company", methods=["GET"])
@require_login
def company_detail():
    """Toon een detailpagina voor de company van de ingelogde gebruiker.

    Deze pagina leest alleen data uit de database.
    Enrichment en competitive landscape zijn al eerder berekend.
    """
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
    """Toon de detailpagina van één specifieke competitor.

    We:
    - controleren of de ID geldig is
    - kijken of de competitor gelinkt is aan de huidige company
    - tonen een eenvoudige detailweergave op basis van bestaande data
    """
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
    """Forceer een volledige refresh van alle competitor signals.

    Belangrijk:
    - POST-route met side-effects (AI-calls, web search, snapshot updates)
    - kan traag zijn, maar is een bewuste actie van de gebruiker
    """
    company = _require_company()
    if not company:
        return redirect(url_for("main.homepage"))

    from services.signals import refresh_competitor_signals

    # Manuele actie: gebruiker verwacht dat AI echt wordt geprobeerd.
    # Gebruik force_ai=True en allow_simple_fallback=False:
    # - Als AI/web search faalt → exception → toon expliciete foutmelding.
    # - Geen stille fallback naar simpele signals (gebruiker moet weten dat AI faalde).
    try:
        refresh_competitor_signals(company, force_ai=True, allow_simple_fallback=False)
        flash("Competitor signals refreshed with AI & web search.", "success")
    except Exception as e:
        # User-triggered actie: altijd feedback geven
        logging.error("Error refreshing competitor signals with AI: %s", e, exc_info=True)
        flash(
            "AI-signals konden niet worden gegenereerd (OpenAI niet beschikbaar of quota opgebruikt). "
            "Bestaande signals blijven zichtbaar, maar zijn niet geüpdatet.",
            "error",
        )

    return redirect(url_for("main.homepage") + "#signals")


@main_bp.route("/refresh-competitors", methods=["POST"])
@require_login
def refresh_competitors_route():
    """Ververs de lijst van competitors met recente OpenAI-data.

    Deze route:
    - roept OpenAI aan om nieuwe competitors te zoeken
    - vervangt bestaande links door de nieuwe set
    - kan traag zijn, maar is een expliciete POST-actie
    """
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