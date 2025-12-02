"""Simplified authentication routes for MVP."""

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func
from app import db
from models import Company, User, CompanyCompetitor
from utils.auth import login_user
from services.company_api import (
    fetch_company_info, 
    apply_company_data, 
    fetch_similar_companies,
    needs_api_fetch,
    link_company_industries
)
from services.competitor_filter import filter_competitors

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
    
    errors = []
    if not first_name:
        errors.append("First name is required.")
    if not last_name:
        errors.append("Last name is required.")
    if not email:
        errors.append("Email is required.")
    if not company_name:
        errors.append("Company name is required.")
    if not company_domain:
        errors.append("Company domain is required.")
    
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
        db.session.flush()
    
    if company_domain and needs_api_fetch(company, company_domain):
        api_data = fetch_company_info(domain=company_domain)
        if api_data:
            apply_company_data(company, api_data)
            link_company_industries(company, api_data.get("industries", []))
            db.session.flush()
            
            # Request more competitors to account for filtering
            # Filter may remove 30-50% due to same-domain, subsidiaries, etc.
            # Request 10 to balance cost (50 credits) with getting ~5 after filtering
            raw_competitors = fetch_similar_companies(domain=company_domain, limit=10)
            filtered_competitors = filter_competitors(company_name, company_domain, raw_competitors)
            # Limit to 5 competitors to keep consistent behavior
            filtered_competitors = filtered_competitors[:5]
            if filtered_competitors:
                for competitor_data in filtered_competitors:
                    competitor_domain = competitor_data.get("domain")
                    competitor_name = competitor_data.get("name") or "Unknown"
                    
                    if not competitor_domain:
                        continue
                    
                    # Check if competitor exists by domain first
                    competitor = db.session.query(Company).filter(
                        Company.domain == competitor_domain
                    ).first()
                    
                    # If not found by domain, check by name (case-insensitive)
                    if not competitor:
                        competitor = db.session.query(Company).filter(
                            func.lower(Company.name) == competitor_name.lower()
                        ).first()
                    
                    if not competitor:
                        competitor = Company()
                        competitor.name = competitor_name
                        competitor.domain = competitor_domain
                        competitor.website = competitor_data.get("website")
                        competitor.headline = competitor_data.get("description")
                        competitor.industry = competitor_data.get("industry")
                        db.session.add(competitor)
                        db.session.flush()
                    else:
                        # Update domain if it's missing but we have it
                        if not competitor.domain and competitor_domain:
                            competitor.domain = competitor_domain
                        # Update other fields if missing
                        if not competitor.website and competitor_data.get("website"):
                            competitor.website = competitor_data.get("website")
                        if not competitor.headline and competitor_data.get("description"):
                            competitor.headline = competitor_data.get("description")
                        if not competitor.industry and competitor_data.get("industry"):
                            competitor.industry = competitor_data.get("industry")
                        db.session.flush()
                    
                    if competitor.id == company.id:
                        continue
                    
                    existing_competitor = db.session.query(CompanyCompetitor).filter(
                        CompanyCompetitor.company_id == company.id,
                        CompanyCompetitor.competitor_id == competitor.id
                    ).first()
                    
                    if not existing_competitor:
                        competitor_link = CompanyCompetitor(
                            company_id=company.id,
                            competitor_id=competitor.id
                        )
                        db.session.add(competitor_link)
                
                db.session.flush()
    
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
