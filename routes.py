"""HTTP route registration and API endpoints for the startup intelligence app.

Philosophy
----------
- Keep route handlers thin: they orchestrate services and serialize results,
  leaving business logic in `services/`.
- Return JSON responses to support both web dashboards and automation hooks.
- Provide health/readiness endpoints for deployment platforms.

Endpoint categories
-------------------
1. Health checks (`/health`) ensure the runtime is reachable.
2. Company read APIs (`/companies`, `/companies/<id>`) feed dashboards.
3. Sync entrypoint (`/sync/company`) triggers Clay ingestion (with optional
   preloaded snapshots).
4. Reporting endpoints aggregate data for weekly digests.
5. Watchdog endpoint exposes diff structures for notifications.

Each route documents expected payloads and responses so frontend engineers and
automation scripts can integrate quickly.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Optional

from flask import (
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from models import (
    Account,
    Company,
    CompanyCompetitor,
    CompanyIndustry,
    Industry,
    Profile,
    Product,
)
from services import ClayClient, ClaySyncService, ReportingService, WatchdogService


def register_routes(app, db):
    """Register JSON-first API endpoints used by the frontend and automation."""

    def _serialize_company(company: Company) -> Dict[str, Any]:
        """Convert a `Company` ORM object into a JSON-ready dictionary.

        Includes related industries, competitors, and products so a single call
        returns the full context needed for dashboards or reports.
        """
        return {
            "id": str(company.id),
            "name": company.name,
            "domain": company.domain,
            "headline": company.headline,
            "funding": company.funding,
            "number_of_employees": company.number_of_employees,
            "external_reference": company.external_reference,
            "last_updated": company.last_updated.isoformat() if company.last_updated else None,
            "source": company.source,
            "industries": [
                {
                    "industry_id": str(link.industry_id),
                    "name": link.industry.name if link.industry else None,
                }
                for link in company.industries
            ],
            "competitors": [
                {
                    "company_id": str(link.competitor_id),
                    "name": link.competitor.name if link.competitor else None,
                    "relationship_type": link.relationship_type,
                }
                for link in company.competitors
            ],
            "products": [
                {
                    "id": str(product.id),
                    "name": product.name,
                    "industry": product.industry.name if product.industry else None,
                    "funding": product.funding,
                }
                for product in company.products
            ],
        }

    def _parse_uuid(value: str) -> uuid.UUID:
        """Parse a UUID string and raise an HTTP 400 on failure."""
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError):
            abort(400, description=f"Invalid UUID value: {value!r}")

    def _set_login_context(profile: Profile) -> None:
        """Persist the session context for the logged-in profile."""
        session["profile_id"] = str(profile.id)
        session["company_id"] = str(profile.company_id)

    def _load_current_company() -> Optional[Company]:
        """Fetch the current company with enriched relationships for the session."""
        company_id = session.get("company_id")
        profile_id = session.get("profile_id")
        if not company_id or not profile_id:
            return None
        try:
            company_uuid = uuid.UUID(company_id)
            profile_uuid = uuid.UUID(profile_id)
        except (TypeError, ValueError):
            session.clear()
            return None

        profile = (
            db.session.query(Profile)
            .options(joinedload(Profile.company))
            .filter(Profile.id == profile_uuid, Profile.company_id == company_uuid)
            .first()
        )
        if profile is None or profile.company is None:
            session.clear()
            return None

        company = (
            db.session.query(Company)
            .options(joinedload(Company.industries).joinedload(CompanyIndustry.industry))
            .options(joinedload(Company.products).joinedload(Product.industry))
            .options(joinedload(Company.competitors).joinedload(CompanyCompetitor.competitor))
            .filter(Company.id == company_uuid)
            .first()
        )
        if company is None:
            session.clear()
            return None

        g.current_profile = profile
        g.current_company = company
        return company

    def _require_company_context() -> Optional[Company]:
        """Ensure a company is loaded for the session, otherwise redirect to login."""
        company = getattr(g, "current_company", None)
        if company is not None:
            return company
        return _load_current_company()

    def company_login_required(view_func):
        """Decorator ensuring a company-scoped session is present."""

        @wraps(view_func)
        def wrapper(*args, **kwargs):
            company = _require_company_context()
            if company is None:
                flash("Log in to view your company's data.", "error")
                return redirect(url_for("login", next=request.path))
            return view_func(*args, **kwargs)

        return wrapper

    @app.before_request
    def _set_globals():
        """Load the current profile/company into `g` if a session exists."""
        if getattr(g, "current_company", None) is not None:
            return
        _load_current_company()

    @app.context_processor
    def _inject_login_context():
        """Expose the logged-in company/profile to templates."""
        return {
            "current_company": getattr(g, "current_company", None),
            "current_profile": getattr(g, "current_profile", None),
        }

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        """Allow a new user to create an account and trigger Clay enrichment."""
        if getattr(g, "current_company", None):
            flash("You're already signed in.", "success")
            return redirect(url_for("homepage"))

        if request.method == "POST":
            first_name = (request.form.get("first_name") or "").strip()
            last_name = (request.form.get("last_name") or "").strip()
            email = (request.form.get("email") or "").strip().lower()
            role = (request.form.get("role") or "").strip()
            phone_number = (request.form.get("phone_number") or "").strip()
            date_of_birth_str = (request.form.get("date_of_birth") or "").strip()
            country = (request.form.get("country") or "").strip()

            company_name = (request.form.get("company_name") or "").strip()
            company_domain = (request.form.get("company_domain") or "").strip().lower()
            company_headline = (request.form.get("company_headline") or "").strip()

            errors = []
            if not first_name:
                errors.append("First name is required.")
            if not last_name:
                errors.append("Last name is required.")
            if not email:
                errors.append("Email is required.")
            if not company_name:
                errors.append("Company name is required.")

            existing_account = None
            if email:
                existing_account = (
                    db.session.query(Account)
                    .filter(func.lower(Account.email) == email)
                    .first()
                )
                if existing_account:
                    errors.append("An account with that email already exists. Please log in instead.")

            date_of_birth = None
            if date_of_birth_str:
                try:
                    date_of_birth = datetime.strptime(date_of_birth_str, "%Y-%m-%d").date()
                except ValueError:
                    errors.append("Date of birth must use the YYYY-MM-DD format.")

            if errors:
                for message in errors:
                    flash(message, "error")
                return render_template("signup.html")

            company = None
            if company_domain:
                company = (
                    db.session.query(Company)
                    .filter(func.lower(Company.domain) == company_domain)
                    .first()
                )
            if company is None:
                company = (
                    db.session.query(Company)
                    .filter(Company.name.ilike(company_name))
                    .first()
                )
            if company is None:
                company = Company(name=company_name)
                db.session.add(company)

            if company_domain:
                company.domain = company_domain
            if company_headline:
                company.headline = company_headline

            account = Account(email=email, is_active=True)
            profile = Profile(
                account=account,
                company=company,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role or None,
                phone_number=phone_number or None,
                date_of_birth=date_of_birth,
                country=country or None,
            )
            db.session.add(profile)

            profile_id = None
            try:
                db.session.commit()
                profile_id = profile.id
            except SQLAlchemyError as exc:
                db.session.rollback()
                flash(f"Could not complete signup: {exc}", "error")
                return render_template("signup.html")

            identifier = company.domain or company.name
            clay_service = ClaySyncService(db.session, clay_client=ClayClient())
            try:
                company = clay_service.sync_company(identifier, source="Clay Signup")
            except NotImplementedError:
                flash(
                    "Clay enrichment is not yet configured. Your profile and company were saved.",
                    "error",
                )
            except SQLAlchemyError as exc:
                db.session.rollback()
                flash(f"Clay enrichment failed: {exc}", "error")
            except Exception as exc:  # safeguard unexpected clay errors
                flash(f"Clay enrichment failed unexpectedly: {exc}", "error")

            refreshed_profile = (
                db.session.query(Profile)
                .options(joinedload(Profile.company))
                .filter(Profile.id == profile_id)
                .first()
            )

            _set_login_context(refreshed_profile or profile)
            flash("Your workspace is ready. Welcome aboard!", "success")
            return redirect(url_for("homepage"))

        return render_template("signup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        """Simple email-based login scoped to the company relationship."""
        if getattr(g, "current_company", None):
            return redirect(url_for("homepage"))
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            if not email:
                flash("Email is required to log in.", "error")
                return render_template("login.html")

            profile = (
                db.session.query(Profile)
                .options(joinedload(Profile.company), joinedload(Profile.account))
                .outerjoin(Profile.account)
                .filter(func.lower(Profile.email) == email, Profile.company_id.isnot(None))
                .first()
            )
            if profile is None:
                flash("We couldn't find an active profile with that email.", "error")
                return render_template("login.html")
            if profile.account and not profile.account.is_active:
                flash("This account is disabled. Contact your administrator.", "error")
                return render_template("login.html")

            _set_login_context(profile)
            flash(f"Welcome back, {profile.first_name}!", "success")
            destination = request.args.get("next") or url_for("homepage")
            return redirect(destination)

        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        """Clear the session and return to the login page."""
        session.clear()
        flash("You have been signed out.", "success")
        return redirect(url_for("login"))

    @app.route("/", methods=["GET"])
    @company_login_required
    def homepage():
        """Render a company-scoped overview dashboard for the logged-in session."""
        company = g.current_company
        team_members = (
            db.session.query(Profile)
            .filter(Profile.company_id == company.id)
            .order_by(Profile.last_name.asc(), Profile.first_name.asc())
            .all()
        )

        metrics = {
            "company_count": 1,
            "profile_count": len(team_members),
            "industry_count": len(company.industries),
            "product_count": len(company.products),
            "total_funding": company.funding or 0,
        }

        top_industries = [
            {"name": link.industry.name, "company_count": 1}
            for link in company.industries
            if link.industry
        ]

        return render_template(
            "index.html",
            company_card=company,
            metrics=metrics,
            top_industries=top_industries,
            highlighted_profiles=team_members,
        )

    @app.route("/health", methods=["GET"])
    def health():
        """Readiness probe used by hosting platforms (e.g., render.com)."""
        return jsonify({"status": "healthy"})

    @app.route("/companies", methods=["GET"])
    def list_companies():
        """Return companies scoped to the logged-in user's company."""
        company = _require_company_context()
        if company is None:
            abort(401, description="Authentication required")
        return jsonify({"companies": [_serialize_company(company)]})

    @app.route("/companies/<company_id>", methods=["GET"])
    def get_company(company_id: str):
        """Return details for a single company identified by UUID."""
        company_uuid = _parse_uuid(company_id)
        company = _require_company_context()
        if company is None:
            abort(401, description="Authentication required")
        if company.id != company_uuid:
            abort(403, description="You cannot access data for that company")
        return jsonify({"company": _serialize_company(company)})

    @app.route("/companies/<company_id>/overview", methods=["GET"])
    @company_login_required
    def company_overview(company_id: str):
        """Render the detailed company overview page."""
        company_uuid = _parse_uuid(company_id)
        company = _require_company_context()
        if company is None or company.id != company_uuid:
            abort(403, description="You cannot access data for that company")

        team_members = (
            db.session.query(Profile)
            .filter(Profile.company_id == company_uuid)
            .order_by(Profile.last_name.asc(), Profile.first_name.asc())
            .all()
        )

        competitor_links = [
            {
                "name": link.competitor.name if link.competitor else None,
                "id": str(link.competitor_id),
                "relationship_type": link.relationship_type,
                "notes": link.notes,
            }
            for link in company.competitors
            if link.competitor
        ]

        return render_template(
            "company_detail.html",
            company=company,
            team_members=team_members,
            competitor_links=competitor_links,
        )

    @app.route("/companies/<company_id>/report", methods=["GET"])
    def company_report(company_id: str):
        """Return the weekly report payload for a company."""
        company_uuid = _parse_uuid(company_id)
        company = _require_company_context()
        if company is None:
            abort(401, description="Authentication required")
        if company.id != company_uuid:
            abort(403, description="You cannot access data for that company")
        reporting_service = ReportingService(db.session)
        try:
            report = reporting_service.generate_company_weekly_report(company_uuid)
        except ValueError as exc:
            abort(404, description=str(exc))
        return jsonify({"report": report})

    @app.route("/reports/companies", methods=["GET"])
    def all_company_reports():
        """Generate reports for every company (use sparingly in production)."""
        company = _require_company_context()
        if company is None:
            abort(401, description="Authentication required")
        reporting_service = ReportingService(db.session)
        report = reporting_service.generate_company_weekly_report(company.id)
        return jsonify({"reports": [report]})

    @app.route("/sync/company", methods=["POST"])
    def sync_company():
        """Trigger a sync from Clay for one company.

        Expected JSON payload (minimal):

        ```
        {
            "identifier": "example.com",
            "snapshot": {...},   # optional pre-fetched Clay bundle
            "source": "Clay"    # optional metadata override
        }
        ```

        Returns the serialized company plus HTTP 202 to signal that work was
        accepted (the operation is synchronous today but may become async later).
        """
        payload = request.get_json(silent=True) or {}
        identifier = (
            payload.get("identifier")
            or payload.get("domain")
            or payload.get("company_id")
            or payload.get("name")
        )
        if not identifier:
            abort(400, description="Payload must include an identifier/domain/name.")

        snapshot = payload.get("snapshot")
        clay_client = ClayClient()
        sync_service = ClaySyncService(db.session, clay_client=clay_client)
        try:
            company = sync_service.sync_company(identifier, snapshot=snapshot, source=payload.get("source", "Clay"))
        except NotImplementedError as exc:
            abort(501, description=str(exc))
        except SQLAlchemyError as exc:
            db.session.rollback()
            abort(500, description=f"Database error: {exc}")

        return jsonify({"company": _serialize_company(company)}), 202

    @app.route("/watchdog/company", methods=["POST"])
    def watchdog_company():
        """Compare a stored company with a fresh Clay snapshot.

        Payload mirrors `/sync/company`; supply `snapshot` to avoid hitting Clay
        during tests.  Response includes a diff map suitable for notifications.
        """
        payload = request.get_json(silent=True) or {}
        identifier = (
            payload.get("identifier")
            or payload.get("domain")
            or payload.get("company_id")
            or payload.get("name")
        )
        if not identifier:
            abort(400, description="Payload must include an identifier/domain/name.")

        snapshot = payload.get("snapshot")
        watchdog_service = WatchdogService(db.session, clay_client=ClayClient())
        try:
            diff = watchdog_service.detect_company_updates(identifier, snapshot=snapshot)
        except NotImplementedError as exc:
            abort(501, description=str(exc))
        return jsonify(diff)

    @app.route("/profiles/<profile_id>", methods=["GET"])
    def get_profile(profile_id: str):
        """Retrieve a profile with account and company relationships."""
        profile_uuid = _parse_uuid(profile_id)
        profile = (
            db.session.query(Profile)
            .options(joinedload(Profile.company))
            .options(joinedload(Profile.account))
            .filter(Profile.id == profile_uuid)
            .first()
        )
        if profile is None:
            abort(404, description=f"Profile {profile_id} not found")

        return jsonify(
            {
                "profile": {
                    "id": str(profile.id),
                    "email": profile.email,
                    "first_name": profile.first_name,
                    "last_name": profile.last_name,
                    "role": profile.role,
                    "phone_number": profile.phone_number,
                    "company_id": str(profile.company_id) if profile.company_id else None,
                    "account_id": str(profile.account_id),
                }
            }
        )