"""Clay API client façade.

Why this module exists:
- Keeps third-party HTTP logic out of view/controller code.
- Provides a consistent return contract (normalized dictionaries) regardless of
  whether we talk to Clay's sandbox, production API, or a cached snapshot.
- Centralizes authentication, retry, and rate-limit handling once the concrete
  integration is implemented.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional
from urllib import error, parse, request


class ClayError(RuntimeError):
    """Raised when Clay returns a non-success response."""


class ClayAuthenticationError(ClayError):
    """Raised when authentication with Clay fails."""


class ClayRateLimitError(ClayError):
    """Raised when Clay signals a rate limit violation."""

    def __init__(self, message: str, *, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ClayTransientError(ClayError):
    """Raised for transient network/HTTP failures that can be retried."""


@dataclass
class ClayClient:
    """Thin wrapper around the Clay API.

    Parameters
    ----------
    api_key:
        Optional Clay API key. Load it from environment variables or a secrets
        manager; do not hardcode secrets in source control.
    base_url:
        Clay REST endpoint. Override via `CLAY_BASE_URL` if your account uses a
        sandbox or regional host.
    timeout:
        Socket timeout (seconds) for the underlying HTTP call.
    max_retries:
        Total attempts for transient failures (including the initial request).
    backoff_factor:
        Base multiplier for exponential backoff between retries.
    """

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: float = 10.0
    max_retries: int = 3
    backoff_factor: float = 0.5
    default_headers: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.getenv("CLAY_API_KEY")
        configured_base_url = self.base_url or os.getenv("CLAY_BASE_URL")
        if configured_base_url:
            self.base_url = configured_base_url.rstrip("/")
        else:
            # Public API base; override via CLAY_BASE_URL when using a sandbox.
            self.base_url = "https://api.clay.com/v1"

        self.timeout = float(os.getenv("CLAY_TIMEOUT", self.timeout))
        self.max_retries = int(os.getenv("CLAY_MAX_RETRIES", self.max_retries))
        self.backoff_factor = float(os.getenv("CLAY_BACKOFF_FACTOR", self.backoff_factor))
        self.company_endpoint = os.getenv("CLAY_COMPANY_ENDPOINT", "/companies/{identifier}")

        headers = {
            "Accept": "application/json",
            "User-Agent": "startup-intelligence-backend/1.0 (+https://example.com)",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self.default_headers = {**headers, **(self.default_headers or {})}

    # --------------------------------------------------------------------- #
    # Public API                                                           #
    # --------------------------------------------------------------------- #
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
        """

        if not identifier or not identifier.strip():
            raise ValueError("Clay identifier must be a non-empty string.")
        identifier = identifier.strip()

        raw_payload = self._request_company_bundle(identifier)
        return self._normalize_payload(raw_payload)

    # --------------------------------------------------------------------- #
    # HTTP helpers                                                          #
    # --------------------------------------------------------------------- #
    def _request_company_bundle(self, identifier: str) -> Dict[str, Any]:
        if not self.api_key:
            raise ClayAuthenticationError(
                "Clay API key not configured. Set CLAY_API_KEY or pass api_key explicitly."
            )

        url = self._build_company_url(identifier)
        headers = dict(self.default_headers)

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                return self._http_get_json(url, headers=headers)
            except ClayRateLimitError as exc:
                last_error = exc
                wait = exc.retry_after or self._compute_backoff(attempt)
                time.sleep(wait)
            except ClayTransientError as exc:
                last_error = exc
                time.sleep(self._compute_backoff(attempt))
        if last_error:
            raise ClayError(f"Failed to fetch Clay bundle after {self.max_retries} attempts.") from last_error
        raise ClayError("Failed to fetch Clay bundle for unknown reasons.")

    def _http_get_json(self, url: str, *, headers: Dict[str, str]) -> Dict[str, Any]:
        """Perform an HTTP GET and decode JSON, raising rich Clay errors."""

        req = request.Request(url, headers=headers, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = response.read()
                return self._decode_json(body, url)
        except error.HTTPError as exc:
            body = exc.read() if exc.fp else b""
            status = exc.code
            if status == 401:
                raise ClayAuthenticationError("Clay API rejected the provided API key.") from exc
            if status == 429:
                retry_after = self._parse_retry_after(exc.headers.get("Retry-After"))
                raise ClayRateLimitError("Clay API rate limit exceeded.", retry_after=retry_after) from exc
            if 500 <= status < 600:
                raise ClayTransientError(f"Clay API returned {status}.") from exc

            details = self._safe_decode_text(body)
            message = f"Clay API returned {status}. Response: {details or '<empty>'}"
            raise ClayError(message) from exc
        except error.URLError as exc:
            raise ClayTransientError(f"Clay API request failed: {exc.reason}") from exc

    def _decode_json(self, payload: bytes, url: str) -> Dict[str, Any]:
        if not payload:
            return {}
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            preview = payload[:200].decode("utf-8", errors="replace")
            raise ClayError(f"Clay API returned non-JSON response from {url}: {preview}") from exc

        if not isinstance(decoded, dict):
            raise ClayError("Clay API returned JSON that is not an object.")
        return decoded

    def _build_company_url(self, identifier: str) -> str:
        query_params = {"include": "company,competitors,industries,products"}
        endpoint = (self.company_endpoint or "").strip() or "/companies/{identifier}"

        # Support Clay lookup endpoints like /companies:lookup that expect query params instead of path params.
        if "{identifier}" not in endpoint or ":lookup" in endpoint:
            # Use query parameter; default Clay lookup uses domain parameter.
            query_params.setdefault("domain", identifier)
            query_string = parse.urlencode(query_params)
            return f"{self.base_url}{endpoint}?{query_string}"

        safe_identifier = parse.quote(identifier, safe="")
        formatted_endpoint = endpoint.format(identifier=safe_identifier)
        query_string = parse.urlencode(query_params)
        return f"{self.base_url}{formatted_endpoint}?{query_string}"

    def _compute_backoff(self, attempt: int) -> float:
        return self.backoff_factor * (2 ** attempt)

    @staticmethod
    def _parse_retry_after(value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_decode_text(value: bytes) -> str:
        if not value:
            return ""
        return value.decode("utf-8", errors="replace").strip()

    # --------------------------------------------------------------------- #
    # Normalization helpers                                                 #
    # --------------------------------------------------------------------- #
    def _normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        container = self._unwrap_payload(payload)

        company_raw = self._coerce_dict(
            container.get("company")
            or container.get("organization")
            or container.get("data")
            or container
        )
        competitors_raw = self._coerce_iterable(
            container.get("competitors")
            or container.get("relationships", {}).get("competitors")
        )
        industries_raw = self._coerce_iterable(
            container.get("industries")
            or container.get("segments")
        )
        products_raw = self._coerce_iterable(container.get("products"))

        normalized = {
            "company": self._compact_dict(self._normalize_company(company_raw)),
            "competitors": [
                self._compact_dict(self._normalize_competitor(item))
                for item in competitors_raw
                if self._normalize_competitor(item)
            ],
            "industries": [
                self._compact_dict(self._normalize_industry(item))
                for item in industries_raw
                if self._normalize_industry(item)
            ],
            "products": [
                self._compact_dict(self._normalize_product(item))
                for item in products_raw
                if self._normalize_product(item)
            ],
        }

        return normalized

    def _unwrap_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        container = self._coerce_dict(payload)
        if "data" in container and isinstance(container["data"], dict):
            container = container["data"]
        if "attributes" in container and isinstance(container["attributes"], dict):
            container = container["attributes"]
        return container

    @staticmethod
    def _coerce_dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _coerce_iterable(value: Any) -> Iterable[Dict[str, Any]]:
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return []

    def _normalize_company(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": data.get("name") or data.get("company_name"),
            "domain": data.get("domain") or data.get("website") or data.get("url"),
            "headline": data.get("headline") or data.get("tagline") or data.get("description"),
            "funding": data.get("funding") or data.get("total_funding") or data.get("funding_total"),
            "employees": data.get("employees") or data.get("employee_count") or data.get("number_of_employees"),
            "clay_id": data.get("clay_id") or data.get("id") or data.get("company_id"),
            "external_reference": data.get("external_reference"),
            "other_criteria": data.get("other_criteria") or data.get("notes"),
        }

    def _normalize_competitor(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        return {
            "name": data.get("name") or data.get("company_name"),
            "domain": data.get("domain") or data.get("website") or data.get("url"),
            "relationship_type": data.get("relationship_type") or data.get("relationship") or data.get("type"),
            "notes": data.get("notes"),
            "clay_id": data.get("clay_id") or data.get("id") or data.get("company_id"),
        }

    def _normalize_industry(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        return {
            "id": data.get("id") or data.get("industry_id"),
            "name": data.get("name") or data.get("label"),
            "value": data.get("value") or data.get("score"),
            "description": data.get("description"),
        }

    def _normalize_product(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        industry_payload = data.get("industry") if isinstance(data.get("industry"), dict) else None
        normalized_industry = self._normalize_industry(industry_payload) if industry_payload else {}

        return {
            "id": data.get("id") or data.get("product_id"),
            "name": data.get("name") or data.get("product_name"),
            "funding": data.get("funding") or data.get("raised"),
            "description": data.get("description"),
            "industry": self._compact_dict(normalized_industry) if normalized_industry else None,
        }

    @staticmethod
    def _compact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in data.items() if value is not None}


__all__ = [
    "ClayClient",
    "ClayError",
    "ClayAuthenticationError",
    "ClayRateLimitError",
    "ClayTransientError",
]


