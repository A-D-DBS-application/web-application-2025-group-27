"""Authenticatie routes - login, signup en logout."""

import logging
from typing import List, Optional, cast

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func

from app import db
from models import Company, User
from services.company_api import fetch_openai_similar_companies
from utils.auth import login_user
from utils.company_helpers import (
    add_competitor_from_data,
    enrich_company_if_needed,
    generate_landscape_if_needed,
    get_company_competitors,
)

auth_bp = Blueprint("auth", __name__)


def _redirect_authenticated():
    """Stuur ingelogde gebruikers altijd naar het dashboard.

    Dit voorkomt dat een ingelogde gebruiker opnieuw het login- of
    signup-scherm ziet. Als niemand is ingelogd, gebeurt er niets.
    """
    if getattr(g, "current_user", None):
        return redirect(url_for("main.homepage"))
    return None


def _render_login(error: Optional[str] = None):
    """Toon de loginpagina, met optionele foutboodschap."""
    if error:
        flash(error, "error")
    return render_template("login.html")


def _render_signup(errors: Optional[List[str]] = None):
    """Toon de signuppagina, met optionele lijst van foutboodschappen."""
    if errors:
        for message in errors:
            flash(message, "error")
    return render_template("signup.html")


# =============================================================================
# Login
# =============================================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Verwerk login van een gebruiker.

    GET:
        - toont enkel het loginformulier
    POST:
        - leest het e-mailadres
        - zoekt de gebruiker in de database
        - controleert of de gebruiker actief is
        - logt de gebruiker in
        - PERFORMANCE: Geen snapshot refresh bij login (alleen bij expliciete refresh knop)
    """
    redirect_resp = _redirect_authenticated()
    if redirect_resp:
        return redirect_resp
    
    # GET: toon simpelweg het formulier
    if request.method != "POST":
        return _render_login()
    
    # POST: lees en valideer het e-mailadres
    email = request.form.get("email", "").strip().lower()
    if not email:
        return _render_login("Email is required.")
    
    # Zoek de gebruiker met dit e-mailadres (en gekoppelde company)
    user = (
        db.session.query(User)
        .filter(func.lower(User.email) == email, User.company_id.isnot(None))
        .first()
    )
    
    if not user:
        # E-mailadres bestaat niet in het systeem
        return _render_login("User not found. Please sign up first.")
    
    if not user.is_active:
        # Account is gedeactiveerd
        return _render_login("Account is disabled.")
    
    # Log de gebruiker in (zet sessie + g.current_user / g.current_company)
    login_user(user)
    
    # PERFORMANCE: Snapshots worden NIET gerefreshed bij login - alleen bij expliciete refresh knop.
    # Dit verbetert login performance aanzienlijk (geen AI calls bij elke login).
    # Gebruikers kunnen handmatig "Refresh Signals" gebruiken wanneer ze nieuwe data willen.
    
    # Na een geslaagde login altijd naar het dashboard (of "next" parameter)
    return redirect(request.args.get("next") or url_for("main.homepage"))


# =============================================================================
# Signup
# =============================================================================

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Registreer een nieuwe gebruiker en maak eventueel een nieuw bedrijf aan.

    GET:
        - toont enkel het signupformulier
    POST:
        - valideert alle verplichte velden
        - zoekt of maakt een Company record
        - verrijkt de company met externe data (niet-blockend)
        - zoekt en voegt concurrenten toe (niet-blockend)
        - genereert een eerste competitive landscape (niet-blockend)
        - maakt de User aan en logt die in
        - triggert een eerste signal-refresh (niet-blockend)
    """
    redirect_resp = _redirect_authenticated()
    if redirect_resp:
        return redirect_resp
    
    # GET: toon simpelweg het formulier
    if request.method != "POST":
        return _render_signup()
    
    # 1. Lees alle formulierdata in en maak strings schoon.
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    company_name = request.form.get("company_name", "").strip()
    company_domain = request.form.get("company_domain", "").strip().lower()
    role = request.form.get("role", "").strip() or None
    
    # 2. Controleer alle verplichte velden.
    required = {"first_name": "First name", "last_name": "Last name", "email": "Email",
                "company_name": "Company name", "company_domain": "Company domain"}
    errors = [f"{label} is required." for field, label in required.items() if not request.form.get(field, "").strip()]
    
    # 3. Controleer of het e-mailadres al bestaat.
    if not errors:
        existing = db.session.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            errors.append("Email already exists. Please log in instead.")
    
    if errors:
        # Toon het formulier opnieuw met foutboodschappen.
        return _render_signup(errors)
    
    # 4. Zoek een bestaande company of maak er één aan.
    company = db.session.query(Company).filter(Company.name.ilike(company_name)).first()
    if not company:
        company = Company()
        company.name = company_name
        company.domain = company_domain
        db.session.add(company)
        db.session.flush()
    
    # 5. Verrijk company data en haal concurrenten op.
    #    Deze stappen zijn belangrijk, maar mogen de signup nooit breken.
    def _safe_call(func, *args, **kwargs):
        """Voer een functie uit zonder dat fouten de signup blokkeren.
        
        Background enrichment (OpenAI calls) mag signup niet blokkeren.
        Fouten worden gelogd maar signup gaat door met basisdata.
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log errors voor debugging, maar blokkeer signup niet
            logging.warning("Background enrichment failed during signup (%s): %s", func.__name__, e, exc_info=True)
            return None
    
    _safe_call(enrich_company_if_needed, company, company_domain)
    
    similar = _safe_call(fetch_openai_similar_companies, company_name=company_name, domain=company_domain, limit=10)
    if similar:
        base_domain = (company_domain or "").lower().strip()
        for comp_data in similar[:5]:
            comp_domain = (comp_data.get("domain") or "").lower().strip()
            if comp_domain and comp_domain != base_domain:
                _safe_call(add_competitor_from_data, company, comp_data)
    
    db.session.flush()
    db.session.refresh(company)
    _safe_call(generate_landscape_if_needed, company)
    
    # 6. Maak de gebruiker aan in de database.
    user = User()
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.company_id = company.id
    user.role = role
    user.is_active = True
    db.session.add(user)
    db.session.commit()
    
    # 7. Log de gebruiker meteen in.
    login_user(user)
    
    # 8. Initialiseer competitor signals (opnieuw niet-blockend).
    from services.signals import refresh_competitor_signals
    _safe_call(refresh_competitor_signals, company)
    
    return redirect(url_for("main.homepage"))


# =============================================================================
# Logout
# =============================================================================

@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Behandel user logout.
    
    Verwijdert alle session data en redirect naar homepage.
    """
    session.clear()
    return redirect(url_for("main.homepage"))
