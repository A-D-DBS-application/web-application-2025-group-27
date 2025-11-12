"""Clay ingestion and normalization services.

Why this module matters:
-----------------------
- Fetches enriched datasets from Clay and persists them into our Supabase
  schema, keeping UUID primary keys and bridge tables in sync.
- Encapsulates all upsert logic so HTTP routes, CLI commands, or background
  jobs can simply call `ClaySyncService.sync_company(...)` without touching ORM
  details.
- Provides consistent metadata updates (`source`, `last_updated`) to power
  reporting and watchdog features.

Lifecycle overview:
-------------------
1. Retrieve (or accept) a Clay snapshot for a company.
2. Upsert the company itself (`company` table).
3. Normalize industries and competitor relationships through bridge tables.
4. Optionally sync product data (future extensions).
5. Commit the session so data is durable in Supabase.

This module intentionally avoids HTTP calls; instead, it collaborates with
`services.clay.ClayClient`.  That separation keeps ingestion testable by
providing canned snapshots and decouples us from Clay's rate limits during local
development.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from models import (
    Company,
    CompanyCompetitor,
    CompanyIndustry,
    Industry,
    Product,
)
from .clay import ClayClient


def _safe_upper(value: Optional[str]) -> Optional[str]:
    """Normalize casing while respecting `None`.

    Parameters
    ----------
    value:
        Optional string that may need to be compared case-insensitively.

    Returns
    -------
    Optional[str]
        Uppercase equivalent for truthy strings; otherwise returns the original
        value (including `None`).

    Notes
    -----
    Helper kept for future use when matching case-insensitive identifiers such
    as Clay's domain keys.  Using a helper keeps comparisons consistent and
    reduces accidental `AttributeError` when `value` is `None`.
    """


@dataclass
class ClaySyncService:
    """Coordinate fetching and storing company data retrieved from Clay.

    Responsibilities
    ----------------
    - Pull a structured bundle from `ClayClient` (or accept a provided snapshot).
    - Upsert the company, industries, competitors, and products matching the
      Supabase schema.
    - Clean up stale bridge-table rows so the database mirrors Clay's latest
      view.

    Design choices
    --------------
    - The service receives a SQLAlchemy `Session` so it can be reused in web
      requests, CLI scripts, or background tasks.
    - We default to the `ClayClient` stub, but callers may inject a mocked
      client or a pre-configured one with API keys.
    """

    session: Session
    clay_client: ClayClient

    def __init__(self, session: Session, clay_client: Optional[ClayClient] = None) -> None:
        """Create the service.

        Parameters
        ----------
        session:
            Active SQLAlchemy session (typically provided by Flask-SQLAlchemy's
            scoped session).
        clay_client:
            Optional client abstraction.  When omitted, the default stub is used.
        """
        self.session = session
        self.clay_client = clay_client or ClayClient()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def sync_company(
        self,
        identifier: str,
        *,
        snapshot: Optional[Dict[str, Any]] = None,
        source: str = "Clay",
    ) -> Company:
        """Sync (or create) a company and its related data.

        Parameters
        ----------
        identifier:
            Domain, external reference, or Clay-specific lookup key for the
            target company.
        snapshot:
            Optional Clay payload matching the dictionary contract described in
            `ClayClient.fetch_company_bundle`.  Pass this when you already have
            the data (e.g., in tests or from a cached JSON file).
        source:
            Metadata tag persisted in `Company.source` (defaults to `"Clay"`).

        Returns
        -------
        Company
            The up-to-date SQLAlchemy instance (attached to the provided
            session), including relationships ready for serialization.

        Transactionality
        ----------------
        - All mutations happen within the caller's session.
        - The service commits at the end of the method.  If you want to compose
          multiple syncs in a single transaction, call `session.begin()` before
          invoking `sync_company` or refactor to expose a `commit` flag.
        """

        payload = snapshot or self.clay_client.fetch_company_bundle(identifier)
        company_payload = payload.get("company") or {}

        company = self._upsert_company(company_payload, source=source)
        industries_payload = payload.get("industries") or []
        competitors_payload = payload.get("competitors") or []
        products_payload = payload.get("products") or []

        self._sync_industries(company, industries_payload, source=source)
        self._sync_competitors(company, competitors_payload, source=source)
        self._sync_products(company, products_payload, source=source)

        self.session.commit()
        self.session.refresh(company)
        return company

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _upsert_company(self, data: Dict[str, Any], *, source: str) -> Company:
        """Create or update a ``Company`` record.

        Lookup strategy
        ----------------
        We attempt multiple identifiers (Clay ID, domain, name, external ref) so
        repeated syncs converge on the same row even if Clay changes the chosen
        identifier.  Lowercase comparisons are handled via SQL's `ILIKE` for
        portability with Supabase (PostgreSQL).

        Metadata updates
        ----------------
        - Keeps existing values when Clay omits a field (avoids wiping data).
        - Updates `source` so downstream reporting can attribute data origin.
        """

        lookup_keys = [
            data.get("id"),
            data.get("company_id"),
            data.get("clay_id"),
            data.get("external_reference"),
            data.get("domain"),
            data.get("name"),
        ]
        company: Optional[Company] = None
        for key in filter(None, lookup_keys):
            company = (
                self.session.query(Company)
                .filter(
                    (Company.external_reference == key)
                    | (Company.domain == key)
                    | (Company.name.ilike(key) if isinstance(key, str) else False)
                )
                .first()
            )
            if company:
                break

        if company is None:
            company = Company(
                name=data.get("name") or data.get("legal_name") or "Unknown company",
            )
            self.session.add(company)

        company.domain = data.get("domain") or company.domain
        company.headline = data.get("headline") or data.get("summary")
        company.number_of_employees = data.get("employees") or data.get("number_of_employees")
        company.funding = data.get("funding")
        company.andere_criteria = data.get("other_criteria") or data.get("notes")
        company.external_reference = (
            data.get("clay_id") or data.get("id") or data.get("external_reference")
        )
        company.source = source or company.source

        return company

    def _sync_industries(
        self,
        company: Company,
        industries_payload: Iterable[Dict[str, Any]],
        *,
        source: str,
    ) -> None:
        """Synchronize industry associations for a company.

        Steps
        -----
        1. Upsert each industry (using `_get_or_create_industry`).
        2. Link the company to the industry through `CompanyIndustry`.
        3. Remove any existing associations not present in the new payload.

        This ensures Supabase mirrors Clay's latest segmentation while keeping
        referential integrity intact.
        """

        existing_links = {
            (link.industry_id): link for link in list(company.industries)
        }
        seen_industries = set()

        for industry_data in industries_payload:
            industry = self._get_or_create_industry(industry_data, source=source)
            seen_industries.add(industry.id)

            if industry.id not in existing_links:
                association = CompanyIndustry(company=company, industry=industry)
                self.session.add(association)

        # Remove stale links
        for link in list(company.industries):
            if link.industry_id not in seen_industries:
                self.session.delete(link)

    def _sync_competitors(
        self,
        company: Company,
        competitors_payload: Iterable[Dict[str, Any]],
        *,
        source: str,
    ) -> None:
        """Synchronize competitor relationships.

        Behaviour
        ---------
        - Competitors are stored as regular `Company` rows (self-referencing
          bridge table).
        - New competitors trigger an upsert followed by creation of a
          `CompanyCompetitor` link.
        - Competitors missing from the latest payload are removed to avoid
          stale relationships.

        Notes
        -----
        Relationship types default to `"competitor"` but the payload may include
        richer labels (e.g., `"primary competitor"`, `"emerging"`).  These are
        preserved for downstream analytics.
        """

        def key(value: Any) -> Any:
            if isinstance(value, dict):
                return value.get("id") or value.get("domain") or value.get("name")
            return value

        current_links = {
            competitor.competitor_id: competitor for competitor in list(company.competitors)
        }
        seen_competitors = set()

        for competitor_data in competitors_payload:
            competitor_company = self._upsert_company(competitor_data, source=source)
            seen_competitors.add(competitor_company.id)

            link = current_links.get(competitor_company.id)
            if link is None:
                link = CompanyCompetitor(
                    company=company,
                    competitor=competitor_company,
                )
                self.session.add(link)

            link.relationship_type = competitor_data.get("relationship_type") or "competitor"
            link.notes = competitor_data.get("notes") or link.notes

        for competitor in list(company.competitors):
            if competitor.competitor_id not in seen_competitors:
                self.session.delete(competitor)

    def _sync_products(
        self,
        company: Company,
        products_payload: Iterable[Dict[str, Any]],
        *,
        source: str,
    ) -> None:
        """Synchronize products for the future extension.

        Rationale
        ---------
        Products are optional today but the structure is ready for future
        product-level competition analysis.  We only perform work when Clay
        provides product metadata.

        Deduplication
        -------------
        Product identity is keyed by lowercase name per company to keep the
        schema simple until product IDs exist upstream.
        """

        if not products_payload:
            return

        existing_by_name = {product.name.lower(): product for product in company.products}
        seen_names = set()

        for product_data in products_payload:
            product_name = (product_data.get("name") or "Unnamed product").strip()
            key = product_name.lower()
            seen_names.add(key)

            product = existing_by_name.get(key)
            if product is None:
                product = Product(company=company, name=product_name)
                self.session.add(product)
                existing_by_name[key] = product

            product.description = product_data.get("description") or product.description
            product.funding = product_data.get("funding") or product.funding
            product.source = source or product.source

            industry_payload = product_data.get("industry")
            if industry_payload:
                industry = self._get_or_create_industry(industry_payload, source=source)
                product.industry = industry

        for product in list(company.products):
            if product.name and product.name.lower() not in seen_names:
                self.session.delete(product)

    def _get_or_create_industry(self, data: Dict[str, Any], *, source: str) -> Industry:
        """Return an industry row, creating it if required.

        Matching strategy
        -----------------
        - Prefer explicit UUID/ID when supplied.
        - Fallback to case-insensitive name matching to reuse existing rows.

        Metadata
        --------
        Updates description/value fields when Clay supplies them and tags the
        row with the latest `source`.
        """

        lookup_keys = [
            data.get("id"),
            data.get("industry_id"),
            data.get("name"),
        ]
        industry: Optional[Industry] = None

        for key in filter(None, lookup_keys):
            industry = (
                self.session.query(Industry)
                .filter(
                    (Industry.id == key)
                    | (Industry.name.ilike(key) if isinstance(key, str) else False)
                )
                .first()
            )
            if industry:
                break

        if industry is None:
            industry = Industry(
                name=data.get("name") or data.get("label") or "Unknown industry",
            )
            self.session.add(industry)

        industry.value = data.get("value") or industry.value
        industry.description = data.get("description") or industry.description
        industry.source = source or industry.source

        return industry

