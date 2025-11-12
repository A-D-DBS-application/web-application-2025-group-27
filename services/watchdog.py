"""Watchdog service for detecting data drift between Clay and Supabase.

Purpose
-------
- Compare stored company records against fresh Clay payloads.
- Produce a concise diff structure that downstream notification systems can
  inspect (email, Slack, etc.).
- Provide a single place to extend the comparison logic as we add more
  dimensions (competitors, industries, products).

The current implementation focuses on top-level company fields.  Extend it over
time to compare bridge tables (competitors/industries) and emit granular change
events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from models import Company
from .clay import ClayClient


@dataclass
class WatchdogService:
    """Detect changes between Clay snapshots and persisted data.

    Works with either live Clay fetches or pre-supplied snapshots.  Accepts the
    caller's SQLAlchemy session so it can be used within web requests or
    background jobs.
    """

    session: Session
    clay_client: ClayClient

    def __init__(self, session: Session, clay_client: Optional[ClayClient] = None) -> None:
        self.session = session
        self.clay_client = clay_client or ClayClient()

    def detect_company_updates(self, identifier: str, *, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Compare the latest Clay snapshot with the stored record.

        Parameters
        ----------
        identifier:
            UUID, domain, external reference, or company name used to find the
            stored record.  Mirrors the lookup strategy used by the ingestion
            service.
        snapshot:
            Optional Clay payload (same contract as `ClayClient`).  When omitted,
            the client fetches the latest data from Clay (currently unimplemented
            stub).

        Returns
        -------
        Dict[str, Any]
            Structure shaped as:
            ```
            {
                "status": "diff" | "missing",
                "company_id": "...",    # when found
                "changes": {"field": {"before": ..., "after": ...}}
            }
            ```
            This payload is designed for straightforward serialization and alert
            generation.
        """

        payload = snapshot or self.clay_client.fetch_company_bundle(identifier)
        company_snapshot = payload.get("company") or {}
        company = self._find_company(identifier)

        if company is None:
            return {"status": "missing", "details": "Company not found locally."}

        changes = {}
        for field in ("name", "domain", "headline", "number_of_employees", "funding"):
            current_value = getattr(company, field)
            snapshot_value = company_snapshot.get(field)
            if snapshot_value is not None and snapshot_value != current_value:
                changes[field] = {"before": current_value, "after": snapshot_value}

        return {"status": "diff", "changes": changes, "company_id": str(company.id)}

    def _find_company(self, identifier: str) -> Optional[Company]:
        """Locate a company by id, domain, name, or external reference.

        Uses a disjunctive filter so callers can pass whichever identifier they
        have at hand (e.g., Supabase UUID or Clay domain).  Returns `None` when
        nothing matches.
        """

        query = self.session.query(Company)
        return (
            query.filter(
                (Company.id == identifier)
                | (Company.external_reference == identifier)
                | (Company.domain == identifier)
                | (Company.name.ilike(identifier))
            )
            .limit(1)
            .one_or_none()
        )

