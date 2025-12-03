"""Authentication routes - login, signup, logout."""

from typing import List, Optional, cast

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_

from app import db
from models import Company, User
from services.company_api import fetch_openai_similar_companies
from utils.auth import login_user
from utils.company_helpers import add_competitor_from_data, enrich_company_if_needed, generate_landscape_if_needed

auth_bp = Blueprint("auth", __name__)


def _redirect_authenticated():
    if getattr(g, "current_user", None):
        return redirect(url_for("main.homepage"))
    return None


def _render_login(error: Optional[str] = None):
    if error:
        flash(error, "error")
    return render_template("login.html")


def _render_signup(errors: Optional[List[str]] = None):
    if errors:
        for message in errors:
            flash(message, "error")
    return render_template("signup.html")


# =============================================================================
# Login
# =============================================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    redirect_resp = _redirect_authenticated()
    if redirect_resp:
        return redirect_resp
    
    if request.method != "POST":
        return _render_login()
    
    email = request.form.get("email", "").strip().lower()
    if not email:
        return _render_login("Email is required.")
    
    user = (
        db.session.query(User)
        .filter(func.lower(User.email) == email, User.company_id.isnot(None))
        .first()
    )
    
    if not user:
        return _render_login("User not found. Please sign up first.")
    
    if not user.is_active:
        return _render_login("Account is disabled.")
    
    # Log in the user
    login_user(user)
    
    # Refresh competitor signals on login
    company_obj = cast(Optional[Company], getattr(user, "company", None))
    if company_obj:
        from services.signals import refresh_competitor_signals
        try:
            refresh_competitor_signals(company_obj)
        except Exception:
            pass  # Don't block login if signal refresh fails
    
    return redirect(request.args.get("next") or url_for("main.homepage"))


# =============================================================================
# Signup
# =============================================================================

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Handle user registration and company creation."""
    redirect_resp = _redirect_authenticated()
    if redirect_resp:
        return redirect_resp
    
    if request.method != "POST":
        return _render_signup()
    
    # Collect form data
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    company_name = request.form.get("company_name", "").strip()
    company_domain = request.form.get("company_domain", "").strip().lower()
    role = request.form.get("role", "").strip() or None
    
    # Validate required fields
    required = {"first_name": "First name", "last_name": "Last name", "email": "Email",
                "company_name": "Company name", "company_domain": "Company domain"}
    errors = [f"{label} is required." for field, label in required.items() if not request.form.get(field, "").strip()]
    
    # Check for existing email
    if not errors:
        existing = db.session.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            errors.append("Email already exists. Please log in instead.")
    
    if errors:
        return _render_signup(errors)
    
    # Find or create company
    company = db.session.query(Company).filter(Company.name.ilike(company_name)).first()
    if not company:
        company = Company()
        company.name = company_name
        company.domain = company_domain
        db.session.add(company)
        db.session.flush()
    
    # Enrich company data (don't fail signup if enrichment fails)
    try:
        enrich_company_if_needed(company, company_domain)
    except Exception:
        pass
    
    # Fetch and link competitors using OpenAI (more accurate than Company Enrich)
    try:
        similar = fetch_openai_similar_companies(company_name=company_name, domain=company_domain, limit=10)
    except Exception:
        similar = []
    base_domain = (company_domain or "").lower().strip()
    for comp_data in similar[:5]:
        comp_domain = (comp_data.get("domain") or "").lower().strip()
        if not comp_domain or comp_domain == base_domain:
            continue
        add_competitor_from_data(company, comp_data)
    
    db.session.flush()
    db.session.refresh(company)
    
    # Generate competitive landscape (don't fail signup if this fails)
    try:
        generate_landscape_if_needed(company)
    except Exception:
        pass
    
    # Create user
    user = User()
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.company_id = company.id
    user.role = role
    user.is_active = True
    db.session.add(user)
    db.session.commit()
    
    login_user(user)
    
    # Initialize competitor signals on signup
    from services.signals import refresh_competitor_signals
    try:
        refresh_competitor_signals(company)
    except Exception:
        pass
    
    return redirect(url_for("main.homepage"))


# =============================================================================
# Logout
# =============================================================================

@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Handle user logout."""
    session.clear()
    return redirect(url_for("main.homepage"))
