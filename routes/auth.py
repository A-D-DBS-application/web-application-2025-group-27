"""Simplified authentication routes for MVP."""

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_

from app import db
from models import Company, User, CompanyCompetitor
from services.company_api import fetch_similar_companies
from services.competitor_filter import filter_competitors
from utils.auth import login_user
from utils.company_helpers import enrich_company_if_needed, generate_landscape_if_needed, get_company_competitors

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login - simple email-based authentication."""
    if getattr(g, "current_user", None):
        return redirect(url_for("main.homepage"))
    
    if request.method != "POST":
        return render_template("login.html")
    
    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Email is required.", "error")
        return render_template("login.html")
    
    user = db.session.query(User).filter(
        func.lower(User.email) == email,
        User.company_id.isnot(None)
    ).first()
    
    if not user:
        flash("User not found. Please sign up first.", "error")
        return render_template("login.html")
    
    if not user.is_active:
        flash("Account is disabled.", "error")
        return render_template("login.html")
    
    login_user(user)
    return redirect(request.args.get("next") or url_for("main.homepage"))


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Handle user registration and company creation - simplified for MVP."""
    if getattr(g, "current_user", None):
        return redirect(url_for("main.homepage"))
    
    if request.method != "POST":
        return render_template("signup.html")
    
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    company_name = request.form.get("company_name", "").strip()
    company_domain = request.form.get("company_domain", "").strip().lower()
    
    # Validate required fields
    required = {
        "first_name": "First name",
        "last_name": "Last name",
        "email": "Email",
        "company_name": "Company name",
        "company_domain": "Company domain"
    }
    errors = [f"{label} is required." for field, label in required.items()
              if not request.form.get(field, "").strip()]
    
    if not errors:
        existing_user = db.session.query(User).filter(func.lower(User.email) == email).first()
        if existing_user:
            errors.append("Email already exists. Please log in instead.")
    
    if errors:
        for error in errors:
            flash(error, "error")
        return render_template("signup.html")
    
    company = db.session.query(Company).filter(Company.name.ilike(company_name)).first()
    if not company:
        company = Company()
        company.name = company_name
        company.domain = company_domain
        db.session.add(company)
        db.session.flush()  # Need ID for competitor linking
    
    enrich_company_if_needed(company, company_domain)
    
    # Fetch and add competitors
    raw_competitors = fetch_similar_companies(domain=company_domain, limit=10)
    filtered_competitors = filter_competitors(company_name, company_domain, raw_competitors)[:5]
    
    for competitor_data in filtered_competitors:
        competitor_domain = competitor_data.get("domain")
        if not competitor_domain:
            continue
        
        competitor_name = competitor_data.get("name") or "Unknown"
        
        # Find competitor by domain or name
        competitor = db.session.query(Company).filter(
            or_(
                Company.domain == competitor_domain,
                func.lower(Company.name) == competitor_name.lower()
            )
        ).first()
        
        if not competitor:
            competitor = Company()
            competitor.name = competitor_name
            competitor.domain = competitor_domain
            competitor.website = competitor_data.get("website")
            competitor.headline = competitor_data.get("description")
            competitor.industry = competitor_data.get("industry")
            db.session.add(competitor)
            db.session.flush()  # Need ID for comparison and linking
        else:
            # Update missing fields
            updates = {
                "domain": competitor_domain,
                "website": competitor_data.get("website"),
                "headline": competitor_data.get("description"),
                "industry": competitor_data.get("industry")
            }
            for field, value in updates.items():
                if value and not getattr(competitor, field):
                    setattr(competitor, field, value)
        
        if competitor.id == company.id:
            continue
        
        # Link competitor if not already linked
        if not db.session.query(CompanyCompetitor).filter(
            CompanyCompetitor.company_id == company.id,
            CompanyCompetitor.competitor_id == competitor.id
        ).first():
            competitor_link = CompanyCompetitor()
            competitor_link.company_id = company.id
            competitor_link.competitor_id = competitor.id
            db.session.add(competitor_link)
    
    db.session.flush()  # Ensure all competitors are flushed before landscape generation
    db.session.refresh(company)  # Refresh to load newly added competitors relationship
    generate_landscape_if_needed(company)
    
    user = User()
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.company = company
    user.role = request.form.get("role", "").strip() or None
    user.is_active = True
    db.session.add(user)
    db.session.commit()
    
    login_user(user)
    return redirect(url_for("main.homepage"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Handle user logout."""
    session.clear()
    return redirect(url_for("main.homepage"))
