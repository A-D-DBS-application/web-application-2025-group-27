from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_
from app import db
from models import Company, User, CompanyCompetitor
from services.company_api import fetch_similar_companies
from services.competitor_filter import filter_competitors
from utils.auth import login_user
from utils.company_helpers import enrich_company_if_needed, generate_landscape_if_needed

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if getattr(g, "current_user", None): return redirect(url_for("main.homepage"))
    if request.method != "POST": return render_template("login.html")
    
    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Email is required.", "error")
        return render_template("login.html")
    
    user = db.session.query(User).filter(func.lower(User.email) == email, User.company_id.isnot(None)).first()
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
    if getattr(g, "current_user", None): return redirect(url_for("main.homepage"))
    if request.method != "POST": return render_template("signup.html")
    
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    company_name = request.form.get("company_name", "").strip()
    company_domain = request.form.get("company_domain", "").strip().lower()
    
    required = {"first_name": "First name", "last_name": "Last name", "email": "Email", "company_name": "Company name", "company_domain": "Company domain"}
    errors = [f"{label} is required." for field, label in required.items() if not request.form.get(field, "").strip()]
    
    if not errors and db.session.query(User).filter(func.lower(User.email) == email).first():
        errors.append("Email already exists. Please log in instead.")
    
    if errors:
        for e in errors: flash(e, "error")
        return render_template("signup.html")
    
    company = db.session.query(Company).filter(Company.name.ilike(company_name)).first()
    if not company:
        company = Company(name=company_name, domain=company_domain)
        db.session.add(company)
        db.session.flush()
    
    enrich_company_if_needed(company, company_domain)
    
    for comp_data in filter_competitors(company_name, company_domain, fetch_similar_companies(domain=company_domain, limit=10))[:5]:
        comp_domain = comp_data.get("domain")
        if not comp_domain: continue
        
        comp_name = comp_data.get("name") or "Unknown"
        competitor = db.session.query(Company).filter(or_(Company.domain == comp_domain, func.lower(Company.name) == comp_name.lower())).first()
        
        if not competitor:
            competitor = Company(name=comp_name, domain=comp_domain, website=comp_data.get("website"), headline=comp_data.get("description"), industry=comp_data.get("industry"))
            db.session.add(competitor)
            db.session.flush()
        else:
            for field, val in [("domain", comp_domain), ("website", comp_data.get("website")), ("headline", comp_data.get("description")), ("industry", comp_data.get("industry"))]:
                if val and not getattr(competitor, field): setattr(competitor, field, val)
        
        if competitor.id != company.id and not db.session.query(CompanyCompetitor).filter(CompanyCompetitor.company_id == company.id, CompanyCompetitor.competitor_id == competitor.id).first():
            db.session.add(CompanyCompetitor(company_id=company.id, competitor_id=competitor.id))
    
    db.session.flush()
    db.session.refresh(company)
    generate_landscape_if_needed(company)
    
    user = User(email=email, first_name=first_name, last_name=last_name, company=company, role=request.form.get("role", "").strip() or None, is_active=True)
    db.session.add(user)
    db.session.commit()
    
    login_user(user)
    return redirect(url_for("main.homepage"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("main.homepage"))
