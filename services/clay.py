"""Clay API client façade.

Why this module exists:
- Keeps third-party HTTP logic out of view/controller code.
- Provides a consistent return contract (normalized dictionaries) regardless of
  whether we talk to Clay's sandbox, production API, or a cached snapshot.
- Centralizes authentication, retry, and rate-limit handling once the concrete
  integration is implemented.

Until the real HTTP connector is wired up, the client simply raises
`NotImplementedError`.  Downstream services accept an optional pre-fetched
`snapshot` argument so you can inject Clay payloads captured via Postman or the
Clay UI during development.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ClayClient:
    """Thin wrapper around the Clay API.

    Parameters
    ----------
    api_key:
        Optional Clay API key.  Load it from environment variables or a secrets
        manager; do not hardcode secrets in source control.

    Implementation sketch
    ---------------------
    - Add an HTTP client (e.g., `httpx` with async support or `requests`).
    - Inject headers (`Authorization: Bearer <key>`) required by Clay.
    - Handle rate limits with exponential backoff.
    - Convert the returned JSON into the normalized dictionary documented below.
    """

    api_key: Optional[str] = None

    def fetch_company_bundle(self, identifier: str) -> Dict[str, Any]:
        """Fetch a full Clay bundle for a single company.

        Parameters
        ----------
        identifier:
            Clay lookup key – typically the company's domain.  This mirrors the
            identifier used by Clay recipes and enrichment jobs.

        Returns
        -------
        Dict[str, Any]
            A normalized dictionary with the following shape (example keys shown;
            you can extend them as Clay adds new fields):

            ```
            {
                "company": {
                    "name": "...",
                    "domain": "...",
                    "funding": 12345,
                    "employees": 42,
                    "headline": "...",
                    ...
                },
                "competitors": [
                    {"name": "...", "domain": "...", "relationship_type": "..."},
                    ...
                ],
                "industries": [
                    {"name": "...", "value": 8, "description": "..."},
                    ...
                ],
                "products": [
                    {"name": "...", "industry": {...}, "funding": 1234},
                    ...
                ],  # optional
            }
            ```

        Raises
        ------
        NotImplementedError
            The concrete Clay integration is not yet implemented.  Downstream
            callers should catch this and respond with HTTP 501 or inject a
            `snapshot` payload during development/testing.
        """

        raise NotImplementedError(
            "Clay API integration not implemented. Provide a snapshot payload or "
            "implement fetch_company_bundle in ClayClient."
        )

