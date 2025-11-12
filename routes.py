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
from typing import Any, Dict, Optional

from flask import abort, jsonify, request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from models import (
    Company,
    CompanyCompetitor,
    CompanyIndustry,
    Product,
    Profile,
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

    @app.route("/", methods=["GET"])
    def root():
        """Simple landing endpoint to verify the API is reachable."""
        return jsonify({"status": "ok", "message": "Startup intelligence API"})

    @app.route("/health", methods=["GET"])
    def health():
        """Readiness probe used by hosting platforms (e.g., render.com)."""
        return jsonify({"status": "healthy"})

    @app.route("/companies", methods=["GET"])
    def list_companies():
        """Return all companies with related industries, competitors, and products."""
        companies = (
            db.session.query(Company)
            .options(joinedload(Company.industries).joinedload(CompanyIndustry.industry))
            .options(joinedload(Company.competitors).joinedload(CompanyCompetitor.competitor))
            .options(joinedload(Company.products).joinedload(Product.industry))
            .all()
        )
        return jsonify({"companies": [_serialize_company(company) for company in companies]})

    @app.route("/companies/<company_id>", methods=["GET"])
    def get_company(company_id: str):
        """Return details for a single company identified by UUID."""
        company_uuid = _parse_uuid(company_id)
        company = (
            db.session.query(Company)
            .options(joinedload(Company.industries).joinedload(CompanyIndustry.industry))
            .options(joinedload(Company.competitors).joinedload(CompanyCompetitor.competitor))
            .options(joinedload(Company.products).joinedload(Product.industry))
            .filter(Company.id == company_uuid)
            .first()
        )
        if company is None:
            abort(404, description=f"Company {company_id} not found")
        return jsonify({"company": _serialize_company(company)})

    @app.route("/companies/<company_id>/report", methods=["GET"])
    def company_report(company_id: str):
        """Return the weekly report payload for a company."""
        company_uuid = _parse_uuid(company_id)
        reporting_service = ReportingService(db.session)
        try:
            report = reporting_service.generate_company_weekly_report(company_uuid)
        except ValueError as exc:
            abort(404, description=str(exc))
        return jsonify({"report": report})

    @app.route("/reports/companies", methods=["GET"])
    def all_company_reports():
        """Generate reports for every company (use sparingly in production)."""
        reporting_service = ReportingService(db.session)
        reports = reporting_service.generate_all_company_reports()
        return jsonify({"reports": reports})

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