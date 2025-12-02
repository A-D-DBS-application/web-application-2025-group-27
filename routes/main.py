import uuid
from flask import Blueprint, g, render_template, redirect, url_for, flash
from app import db
from models import User, CompanyCompetitor
from utils.auth import require_login
from utils.company_helpers import get_company_industries, get_company_competitors, enrich_company_if_needed, generate_landscape_if_needed

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
def homepage():
    """Display landing page for non-logged-in users, main dashboard for logged-in users."""
    if not getattr(g, "current_user", None):
        return render_template("landing.html")
    
    company = g.current_company
    if not company:
        return render_template("index.html", company=None, users=[], metrics={})
    
    team_members = db.session.query(User).filter(User.company_id == company.id, User.is_active == True).order_by(User.last_name.asc(), User.first_name.asc()).all()
    
    competitor_view_models = []
    for link in company.competitors:
        if link and link.competitor:
            comp = link.competitor
            if not comp.number_of_employees and comp.domain:
                try: enrich_company_if_needed(comp, comp.domain)
                except Exception: pass
            competitor_view_models.append({"company": comp, "link": link})
    
    try: db.session.commit()
    except Exception: db.session.rollback()
    
    return render_template("index.html", company=company, users=team_members, industries=get_company_industries(company),
        metrics={"user_count": len(team_members), "competitor_count": len(get_company_competitors(company)),
                 "industry_count": len(get_company_industries(company)), "total_funding": company.funding or 0},
        competitor_view_models=competitor_view_models)


@main_bp.route("/company", methods=["GET"])
@require_login
def company_detail():
    company = g.current_company
    if not company:
        flash("Company not found.", "error")
        return redirect(url_for("main.homepage"))
    
    enrich_company_if_needed(company)
    generate_landscape_if_needed(company)
    db.session.commit()
    return render_template("company_detail.html", company_obj=company, industries=get_company_industries(company), is_competitor=False)


@main_bp.route("/competitor/<competitor_id>", methods=["GET"])
@require_login
def competitor_detail(competitor_id):
    company = g.current_company
    if not company:
        flash("Company not found.", "error")
        return redirect(url_for("main.homepage"))
    
    try: competitor_uuid = uuid.UUID(competitor_id)
    except (TypeError, ValueError):
        flash("Invalid competitor ID.", "error")
        return redirect(url_for("main.homepage"))
    
    link = db.session.query(CompanyCompetitor).filter(CompanyCompetitor.company_id == company.id, CompanyCompetitor.competitor_id == competitor_uuid).first()
    if not link or not link.competitor:
        flash("Competitor not found.", "error")
        return redirect(url_for("main.homepage"))
    
    enrich_company_if_needed(link.competitor)
    generate_landscape_if_needed(link.competitor)
    db.session.commit()
    return render_template("company_detail.html", company_obj=link.competitor, industries=get_company_industries(link.competitor), is_competitor=True)


@main_bp.route("/about", methods=["GET"])
def about():
    """Display about page with founder information."""
    from flask import url_for
    founders = [
        {"name": "Leo He", "role": "Co-founder", "image": url_for('static', filename='images/founders/6254D7A5-E3E1-4782-B39C-63BDC5D53FD4_1_105_c.jpeg')},
        {"name": "Nathan Denys", "role": "Co-founder", "image": url_for('static', filename='images/founders/nathan-denys.jpg')},
        {"name": "Jean Knecht", "role": "Co-founder", "image": url_for('static', filename='images/founders/IMG_2696.JPG')},
        {"name": "Niels Herreman", "role": "Co-founder", "image": url_for('static', filename='images/founders/niels-herreman.jpg')},
        {"name": "Mattis Malfait", "role": "Co-founder", "image": url_for('static', filename='images/founders/mattis-malfait.jpg')},
        {"name": "Jeroen Vroman", "role": "Co-founder", "image": url_for('static', filename='images/founders/jeroen-vroman.jpg')},
    ]
    return render_template("about.html", founders=founders)


@main_bp.route("/health", methods=["GET"])
def health():
    return "OK", 200
