"""Authentication routes - login, signup, logout."""

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_

from app import db
from models import Company, CompanyCompetitor, User
from services.company_api import fetch_openai_similar_companies
from services.competitor_filter import filter_competitors
from utils.auth import login_user
from utils.company_helpers import enrich_company_if_needed, generate_landscape_if_needed

auth_bp = Blueprint("auth", __name__)


# =============================================================================
# Login
# =============================================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if getattr(g, "current_user", None):
        return redirect(url_for("main.homepage"))
    
    if request.method != "POST":
        return render_template("login.html")
    
    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Email is required.", "error")
        return render_template("login.html")
    
    user = (
        db.session.query(User)
        .filter(func.lower(User.email) == email, User.company_id.isnot(None))
        .first()
    )
    
    if not user:
        flash("User not found. Please sign up first.", "error")
        return render_template("login.html")
    
    if not user.is_active:
        flash("Account is disabled.", "error")
        return render_template("login.html")
    
    # Log in the user
    login_user(user)
    
    # Refresh competitor signals on login
    if user.company:
        from services.signals import refresh_competitor_signals
        try:
            refresh_competitor_signals(user.company)
        except Exception:
            pass  # Don't block login if signal refresh fails
    
    return redirect(request.args.get("next") or url_for("main.homepage"))


# =============================================================================
# Signup
# =============================================================================

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Handle user registration and company creation."""
    if getattr(g, "current_user", None):
        return redirect(url_for("main.homepage"))
    
    if request.method != "POST":
        return render_template("signup.html")
    
    # Collect form data
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    company_name = request.form.get("company_name", "").strip()
    company_domain = request.form.get("company_domain", "").strip().lower()
    role = request.form.get("role", "").strip() or None
    
    # Validate required fields
    required = {
        "first_name": "First name",
        "last_name": "Last name",
        "email": "Email",
        "company_name": "Company name",
        "company_domain": "Company domain",
    }
    errors = [
        f"{label} is required."
        for field, label in required.items()
        if not request.form.get(field, "").strip()
    ]
    
    # Check for existing email
    if not errors:
        existing = db.session.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            errors.append("Email already exists. Please log in instead.")
    
    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("signup.html")
    
    # Find or create company
    company = db.session.query(Company).filter(Company.name.ilike(company_name)).first()
    if not company:
        company = Company(name=company_name, domain=company_domain)
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
        filtered = filter_competitors(company_name, company_domain, similar)[:5]
    except Exception:
        similar = []
        filtered = []
    
    for comp_data in filtered:
        comp_domain = comp_data.get("domain")
        if not comp_domain:
            continue
        
        comp_name = comp_data.get("name") or "Unknown"
        
        # Find or create competitor
        competitor = (
            db.session.query(Company)
            .filter(or_(
                Company.domain == comp_domain,
                func.lower(Company.name) == comp_name.lower(),
            ))
            .first()
        )
        
        if not competitor:
            competitor = Company(
                name=comp_name,
                domain=comp_domain,
                website=comp_data.get("website"),
                headline=comp_data.get("description"),
                industry=comp_data.get("industry"),
            )
            db.session.add(competitor)
            db.session.flush()
        else:
            # Update missing fields
            for field, val in [
                ("domain", comp_domain),
                ("website", comp_data.get("website")),
                ("headline", comp_data.get("description")),
                ("industry", comp_data.get("industry")),
            ]:
                if val and not getattr(competitor, field):
                    setattr(competitor, field, val)
        
        # Enrich competitor with OpenAI data (team size, description, funding)
        try:
            enrich_company_if_needed(competitor, comp_domain)
        except Exception:
            pass  # Don't fail if enrichment fails
        
        # Link competitor if not already linked
        if competitor.id != company.id:
            existing_link = (
                db.session.query(CompanyCompetitor)
                .filter(
                    CompanyCompetitor.company_id == company.id,
                    CompanyCompetitor.competitor_id == competitor.id,
                )
                .first()
            )
            if not existing_link:
                db.session.add(CompanyCompetitor(
                    company_id=company.id,
                    competitor_id=competitor.id,
                ))
    
    db.session.flush()
    db.session.refresh(company)
    
    # Generate competitive landscape (don't fail signup if this fails)
    try:
        generate_landscape_if_needed(company)
    except Exception:
        pass
    
    # Create user
    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        company=company,
        role=role,
        is_active=True,
    )
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
