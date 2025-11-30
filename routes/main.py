"""Main application routes - simplified for MVP."""

import uuid
from flask import Blueprint, g, render_template, redirect, url_for, flash
from app import db
from models import User, Company, CompanyCompetitor
from utils.auth import require_login
from services.company_api import (
    fetch_company_info, 
    apply_company_data,
    needs_api_fetch,
    link_company_industries
)

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
@require_login
def homepage():
    """Display the main dashboard - simplified for MVP."""
    try:
        company = g.current_company
        
        if not company:
            return render_template("index.html", company=None, users=[], metrics={})
        
        team_members = db.session.query(User).filter(
            User.company_id == company.id,
            User.is_active == True
        ).order_by(User.last_name.asc(), User.first_name.asc()).all()
        
        competitor_count = len(company.competitors) if company.competitors else 0
        industries = [link.industry for link in company.industries if link and link.industry] if company.industries else []
        
        competitor_view_models = []
        data_fetched = False
        competitors_list = list(company.competitors) if company.competitors else []
        for link in competitors_list:
            if link and link.competitor:
                competitor = link.competitor
                
                # Fetch competitor data from API if employee count is missing and domain exists
                try:
                    if not competitor.number_of_employees and competitor.domain and needs_api_fetch(competitor, competitor.domain):
                        api_data = fetch_company_info(domain=competitor.domain)
                        if api_data:
                            apply_company_data(competitor, api_data)
                            link_company_industries(competitor, api_data.get("industries", []))
                            db.session.flush()
                            data_fetched = True
                except Exception:
                    # If API fetch fails, continue without it - don't crash the page
                    db.session.rollback()
                
                competitor_view_models.append({
                    "company": competitor,
                    "link": link,
                })
        
        # Commit any API-fetched data
        if data_fetched:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        
        metrics = {
            "user_count": len(team_members),
            "competitor_count": competitor_count,
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
        )
    except Exception as e:
        db.session.rollback()
        import traceback
        flash(f"Error loading homepage: {str(e)}", "error")
        return f"Error: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500


@main_bp.route("/company", methods=["GET"])
@require_login
def company_detail():
    """Display detailed information about the user's own company.
    
    Uses the same template as competitor detail but for own company.
    """
    company = g.current_company
    
    if not company:
        flash("Company not found.", "error")
        return redirect(url_for("main.homepage"))
    
    if company.domain and needs_api_fetch(company, company.domain):
        api_data = fetch_company_info(domain=company.domain)
        if api_data:
            apply_company_data(company, api_data)
            link_company_industries(company, api_data.get("industries", []))
            db.session.commit()
    
    industries = [link.industry for link in company.industries if link and link.industry]
    
    return render_template(
        "company_detail.html",
        company_obj=company,
        industries=industries,
        is_competitor=False,
    )


@main_bp.route("/competitor/<competitor_id>", methods=["GET"])
@require_login
def competitor_detail(competitor_id):
    """Display detailed information about a competitor company.
    
    Fetches full company data from API if domain is available and data is missing.
    This is a separate page from the company's own dashboard.
    """
    company = g.current_company
    
    if not company:
        flash("Company not found.", "error")
        return redirect(url_for("main.homepage"))
    
    try:
        competitor_uuid = uuid.UUID(competitor_id)
    except (TypeError, ValueError):
        flash("Invalid competitor ID.", "error")
        return redirect(url_for("main.homepage"))
    
    competitor_link = db.session.query(CompanyCompetitor).filter(
        CompanyCompetitor.company_id == company.id,
        CompanyCompetitor.competitor_id == competitor_uuid
    ).first()
    
    if not competitor_link or not competitor_link.competitor:
        flash("Competitor not found.", "error")
        return redirect(url_for("main.homepage"))
    
    competitor = competitor_link.competitor
    
    # Fetch full company data from API if needed
    if competitor.domain and needs_api_fetch(competitor, competitor.domain):
        api_data = fetch_company_info(domain=competitor.domain)
        if api_data:
            apply_company_data(competitor, api_data)
            link_company_industries(competitor, api_data.get("industries", []))
            db.session.commit()
    
    competitor_industries = [link.industry for link in competitor.industries if link and link.industry]
    
    return render_template(
        "company_detail.html",
        company_obj=competitor,
        industries=competitor_industries,
        is_competitor=True,
    )


@main_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return "OK", 200
