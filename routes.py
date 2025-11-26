"""HTTP route registration for the startup intelligence app."""

import json
import re
import uuid
from datetime import datetime
from functools import wraps
from typing import Optional

from flask import (
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func

from models import Account, Company, CompanyCompetitor, CompanyIndustry, Industry, Profile
from services.company_api import fetch_company_info, fetch_similar_companies


def register_routes(app, db):

    def login_user(profile):
        session["profile_id"] = str(profile.id)
        session["company_id"] = str(profile.company_id)

    def get_current_company():
        company_id = session.get("company_id")
        if not company_id:
            g.current_company = None
            return None
        
        try:
            company_uuid = uuid.UUID(company_id)
        except (TypeError, ValueError):
            session.clear()
            g.current_company = None
            return None

        company = db.session.query(Company).filter(Company.id == company_uuid).first()
        if company:
            g.current_company = company
            profile_id = session.get("profile_id")
            if profile_id:
                try:
                    profile_uuid = uuid.UUID(profile_id)
                    profile = db.session.query(Profile).filter(Profile.id == profile_uuid).first()
                    if profile:
                        g.current_profile = profile
                except (TypeError, ValueError):
                    pass
        else:
            session.clear()
            g.current_company = None
        
        return company

    def require_login(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            company = getattr(g, "current_company", None)
            if not company:
                flash("Please log in.", "error")
                return redirect(url_for("login", next=request.path))
            return view_func(*args, **kwargs)
        return wrapper

    @app.before_request
    def load_user():
        if not hasattr(g, "current_company"):
            get_current_company()

    @app.context_processor
    def add_to_templates():
        return {
            "current_company": getattr(g, "current_company", None),
            "current_profile": getattr(g, "current_profile", None),
        }

    def _parse_int(value):
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            digits = re.findall(r"\d+", value)
            if not digits:
                return None
            number = digits[-1]
            multiplier = 1
            lowered = value.lower()
            if "k" in lowered:
                multiplier = 1_000
            elif "m" in lowered:
                multiplier = 1_000_000
            elif "b" in lowered:
                multiplier = 1_000_000_000
            return int(number) * multiplier
        return None

    def _metadata_blob(candidate):
        metadata = {}
        for key in ("keywords", "categories", "technologies"):
            value = candidate.get(key)
            if isinstance(value, list) and value:
                metadata[key] = value
        for key in ("description", "website", "logo_url", "founded_year", "revenue"):
            value = candidate.get(key)
            if value:
                metadata[key] = value
        location = candidate.get("location")
        if isinstance(location, dict) and location:
            metadata["location"] = location
        return json.dumps(metadata, ensure_ascii=False) if metadata else None

    def _format_notes(candidate, domain: Optional[str]):
        parts = ["Seeded via Company Enrich Similar Companies API"]
        if domain:
            parts.append(f"domain: {domain}")
        funding = candidate.get("funding")
        if funding:
            parts.append(f"funding: {funding:,}" if isinstance(funding, int) else f"funding: {funding}")
        website = candidate.get("website")
        if website:
            parts.append(f"website: {website}")
        return " | ".join(parts)

    def _collect_industry_names(source):
        names = []
        for candidate in source:
            items = candidate.get("industries")
            if isinstance(items, list):
                for entry in items:
                    if isinstance(entry, str) and entry.strip():
                        names.append(entry.strip())
        return names

    def _apply_company_metadata(company, data, allow_overwrite=False):
        if not company or not data:
            return

        def assign(attr, value):
            if value is None:
                return
            current = getattr(company, attr)
            if current and not allow_overwrite:
                return
            setattr(company, attr, value)

        assign("domain", data.get("domain"))
        assign("name", data.get("name"))
        assign("headline", data.get("description"))

        employees = _parse_int(data.get("employees"))
        if employees:
            assign("number_of_employees", employees)

        funding_value = data.get("funding")
        if isinstance(funding_value, str):
            funding_value = _parse_int(funding_value)
        if funding_value:
            assign("funding", funding_value)

        assign("industry", data.get("industry"))
        assign("country", data.get("country"))
        assign("source", "CompanyEnrich")

        metadata = _metadata_blob(data)
        if metadata:
            assign("andere_criteria", metadata)

    def _sync_competitors(company, competitor_candidates):
        """Persist competitor companies and bridge-table entries."""

        if not company or not competitor_candidates:
            return

        for candidate in competitor_candidates:
            if not isinstance(candidate, dict):
                continue

            candidate_domain = (candidate.get("domain") or "").strip().lower()
            candidate_name = (candidate.get("name") or "").strip()

            if candidate_domain and company.domain and candidate_domain == company.domain.lower():
                continue
            if candidate_name and candidate_name.lower() == (company.name or "").lower():
                continue

            competitor = None
            if candidate_domain:
                competitor = (
                    db.session.query(Company)
                    .filter(func.lower(Company.domain) == candidate_domain)
                    .first()
                )
            if not competitor and candidate_name:
                competitor = (
                    db.session.query(Company)
                    .filter(Company.name.ilike(candidate_name))
                    .first()
                )

            if competitor is None:
                competitor = Company()
                competitor.name = candidate_name or (candidate_domain or "Similar Company")
                db.session.add(competitor)

            if candidate_domain:
                competitor.domain = candidate_domain
            competitor.source = "CompanyEnrich Similar"
            if candidate.get("id"):
                competitor.external_reference = candidate.get("id")
            competitor.headline = candidate.get("description") or competitor.headline
            employee_count = _parse_int(candidate.get("employees"))
            if employee_count:
                competitor.number_of_employees = employee_count
            funding_value = candidate.get("funding")
            if isinstance(funding_value, str):
                funding_value = _parse_int(funding_value)
            if funding_value:
                competitor.funding = funding_value
            competitor.industry = candidate.get("industry") or competitor.industry
            competitor.country = candidate.get("country") or competitor.country
            metadata = _metadata_blob(candidate)
            if metadata:
                competitor.andere_criteria = metadata

            existing_link = next(
                (link for link in company.competitors if link.competitor_id == competitor.id),
                None,
            )
            if existing_link:
                continue

            competitor_link = CompanyCompetitor()
            competitor_link.company = company  # type: ignore[assignment]
            competitor_link.competitor = competitor  # type: ignore[assignment]
            competitor_link.relationship_type = "similar"
            competitor_link.notes = _format_notes(candidate, candidate_domain)
            db.session.add(competitor_link)

            if candidate.get("industries"):
                _sync_industries(competitor, candidate.get("industries"))
    def _sync_industries(company, industry_names):
        """Attach industries to the company via the bridge table."""

        if not company or not industry_names:
            return

        normalized = []
        seen = set()
        for name in industry_names:
            if not isinstance(name, str):
                continue
            clean = name.strip()
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(clean)

        existing_links = {
            (link.industry.name.lower() if link.industry else None): link
            for link in company.industries
        }

        for name in normalized:
            if name.lower() in existing_links:
                continue
            industry = (
                db.session.query(Industry)
                .filter(func.lower(Industry.name) == name.lower())
                .first()
            )
            if industry is None:
                industry = Industry()
                industry.name = name
                industry.source = "CompanyEnrich"
                db.session.add(industry)

            association = CompanyIndustry()
            association.company = company  # type: ignore[assignment]
            association.industry = industry  # type: ignore[assignment]
            db.session.add(association)

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if getattr(g, "current_company", None):
            return redirect(url_for("homepage"))

        if request.method != "POST":
            return render_template("signup.html")

        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        company_name = request.form.get("company_name", "").strip()

        errors = []
        if not first_name:
            errors.append("First name is required.")
        if not last_name:
            errors.append("Last name is required.")
        if not email:
            errors.append("Email is required.")
        if not company_name:
            errors.append("Company name is required.")

        existing_account = db.session.query(Account).filter(func.lower(Account.email) == email).first()
        if existing_account:
            errors.append("Email already exists. Please log in instead.")

        date_of_birth = None
        date_str = request.form.get("date_of_birth", "").strip()
        if date_str:
            try:
                date_of_birth = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                errors.append("Date must be YYYY-MM-DD format.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("signup.html")

        company_domain = request.form.get("company_domain", "").strip().lower()
        
        # Try to find existing company by domain or name
        company = None
        if company_domain:
            company = db.session.query(Company).filter(func.lower(Company.domain) == company_domain).first()
        if not company:
            company = db.session.query(Company).filter(Company.name.ilike(company_name)).first()
        
        # Create new company if not found
        if not company:
            company = Company()
            company.name = company_name
            db.session.add(company)
        
        similar_companies = []
        # Fetch company info from API if domain provided
        industry_names = []
        primary_snapshot = None
        if company_domain:
            api_data = fetch_company_info(domain=company_domain)
            if api_data:
                primary_snapshot = api_data
                _apply_company_metadata(company, api_data)
                industry_names = api_data.get("industries") or []

        lookup_value = company.domain or company_domain
        lookup_domain = lookup_value.strip().lower() if isinstance(lookup_value, str) else None
        if lookup_domain:
            similar_companies = fetch_similar_companies(domain=lookup_domain, limit=5)
            if not primary_snapshot and similar_companies:
                primary_snapshot = {**similar_companies[0]}
        
        # Use form data as fallback
        if company_domain and not company.domain:
            company.domain = company_domain
        
        form_headline = request.form.get("company_headline", "").strip()
        if form_headline and not company.headline:
            company.headline = form_headline

        account = Account()
        account.email = email
        account.is_active = True

        profile = Profile()
        profile.account = account  # type: ignore[assignment]
        profile.company = company  # type: ignore[assignment]
        profile.email = email
        profile.first_name = first_name
        profile.last_name = last_name
        profile.role = request.form.get("role", "").strip() or None
        profile.phone_number = request.form.get("phone_number", "").strip() or None
        profile.date_of_birth = date_of_birth
        profile.country = request.form.get("country", "").strip() or None
        db.session.add(profile)
        db.session.flush()

        if not industry_names and similar_companies:
            industry_names = _collect_industry_names(similar_companies)

        if primary_snapshot:
            _apply_company_metadata(company, primary_snapshot, allow_overwrite=True)

        if industry_names:
            _sync_industries(company, industry_names)

        if similar_companies:
            _sync_competitors(company, similar_companies)

        db.session.commit()

        login_user(profile)
        return redirect(url_for("homepage"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if getattr(g, "current_company", None):
            return redirect(url_for("homepage"))
        
        if request.method != "POST":
            return render_template("login.html")

        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Email is required.", "error")
            return render_template("login.html")

        profile = db.session.query(Profile).filter(
            func.lower(Profile.email) == email,
            Profile.company_id.isnot(None)
        ).first()
        
        if not profile:
            flash("Profile not found.", "error")
            return render_template("login.html")
        
        account = db.session.query(Account).filter(Account.id == profile.account_id).first()
        if account and not account.is_active:
            flash("Account is disabled.", "error")
            return render_template("login.html")

        login_user(profile)
        return redirect(request.args.get("next") or url_for("homepage"))

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/", methods=["GET"])
    @require_login
    def homepage():
        company = g.current_company
        team_members = db.session.query(Profile).filter(
            Profile.company_id == company.id
        ).order_by(Profile.last_name.asc(), Profile.first_name.asc()).all()

        industries = []
        for link in company.industries:
            if link.industry:
                industries.append({"name": link.industry.name})

        return render_template(
            "index.html",
            company_card=company,
            metrics={
                "profile_count": len(team_members),
                "industry_count": len(company.industries),
                "product_count": len(company.products),
                "total_funding": company.funding or 0,
            },
            top_industries=industries,
            highlighted_profiles=team_members,
        )

    @app.route("/health", methods=["GET"])
    def health():
        return "OK", 200

    @app.route("/companies", methods=["GET"])
    @require_login
    def list_companies():
        return redirect(url_for("company_overview", company_id=str(g.current_company.id)))

    @app.route("/companies/<company_id>", methods=["GET"])
    @require_login
    def get_company(company_id: str):
        try:
            uuid.UUID(company_id)
        except (TypeError, ValueError):
            abort(400)
        
        if str(g.current_company.id) != company_id:
            abort(403)
        
        return redirect(url_for("company_overview", company_id=company_id))

    @app.route("/companies/<company_id>/overview", methods=["GET"])
    @require_login
    def company_overview(company_id: str):
        try:
            uuid.UUID(company_id)
        except (TypeError, ValueError):
            abort(400)

        if str(g.current_company.id) != company_id:
            abort(403)

        team_members = db.session.query(Profile).filter(
            Profile.company_id == g.current_company.id
        ).order_by(Profile.last_name.asc(), Profile.first_name.asc()).all()

        competitors = []
        for link in g.current_company.competitors:
            if link.competitor:
                competitors.append({
                    "name": link.competitor.name,
                    "relationship_type": link.relationship_type,
                    "notes": link.notes,
                })

        return render_template(
            "company_detail.html",
            company=g.current_company,
            team_members=team_members,
            competitor_links=competitors,
        )

    @app.route("/profiles/<profile_id>", methods=["GET"])
    @require_login
    def get_profile(profile_id: str):
        try:
            profile_uuid = uuid.UUID(profile_id)
        except (TypeError, ValueError):
            abort(400)
        
        profile = db.session.query(Profile).filter(Profile.id == profile_uuid).first()
        if not profile or profile.company_id != g.current_company.id:
            abort(404)

        return render_template("profile_detail.html", profile=profile)