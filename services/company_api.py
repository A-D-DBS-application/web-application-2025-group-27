"""Client helpers for Company Enrich APIs.

The endpoints covered here map to the *Company Enrichment* and *Similar
Companies* APIs documented at https://docs.companyenrich.com/docs/getting-started
so that the signup flow can enrich a workspace with baseline competitors.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Iterable, List, Optional, Union

JsonDict = Dict[str, object]
JsonList = List[object]


_API_KEY_ENVS: Iterable[str] = (
    "COMPANY_ENRICH_API_KEY",
    "ABSTRACT_API_KEY",  # backwards compatibility with the previous integration
)
_DEFAULT_BASE_URLS: Iterable[str] = (
    "https://api.companyenrich.com",
    "https://companyenrichment.abstractapi.com",
)
_ENRICH_PATH_CANDIDATES: Iterable[str] = (
    os.getenv("COMPANY_ENRICH_ENRICH_PATH") or "/v1/company-enrichment",
    "/v1",
    "/v1/company",
)
_ENRICH_POST_PATHS: Iterable[str] = (
    os.getenv("COMPANY_ENRICH_ENRICH_POST_PATH") or "/companies/enrich",
    "/v1/companies/enrich",
    "/companies/enrich/",
)
_SIMILAR_PATH_CANDIDATES: Iterable[str] = (
    os.getenv("COMPANY_ENRICH_SIMILAR_PATH") or "/v1/similar-companies",
    "/v1/similar",
    "/v1/similar-companies/",
)
_SIMILAR_POST_PATHS: Iterable[str] = (
    os.getenv("COMPANY_ENRICH_SIMILAR_POST_PATH") or "/companies/similar",
    "/v1/companies/similar",
    "/companies/similar/",
)
_TIMEOUT = float(os.getenv("COMPANY_ENRICH_TIMEOUT", "10"))


def _load_api_key() -> Optional[str]:
    for env_name in _API_KEY_ENVS:
        api_key = os.getenv(env_name)
        if api_key:
            return api_key

    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
        for env_name in _API_KEY_ENVS:
            api_key = os.getenv(env_name)
            if api_key:
                return api_key
    except ImportError:
        pass

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as env_file:
                for line in env_file:
                    for env_name in _API_KEY_ENVS:
                        if line.startswith(f"{env_name}="):
                            os.environ[env_name] = line.split("=", 1)[1].strip()
                            return os.getenv(env_name)
        except OSError:
            return None

    for env_name in _API_KEY_ENVS:
        value = os.getenv(env_name)
        if value:
            return value
    return None


def _base_candidates() -> List[str]:
    base_overrides = os.getenv("COMPANY_ENRICH_BASE_URL")
    base_candidates: List[str] = []
    if base_overrides:
        base_candidates.append(base_overrides)
    base_candidates.extend(_DEFAULT_BASE_URLS)
    return base_candidates


def _build_urls(path: str, params: Dict[str, str]) -> List[str]:
    api_key = _load_api_key()
    if not api_key:
        return []

    urls: List[str] = []
    safe_params = {k: v for k, v in params.items() if v not in (None, "")}
    safe_params["api_key"] = api_key
    query_string = urllib.parse.urlencode(safe_params)

    path = path if path.startswith("/") else f"/{path}"
    for base_url in _base_candidates():
        normalized = base_url.rstrip("/")
        urls.append(f"{normalized}{path}?{query_string}")
    return urls


def _request(paths: Iterable[str], params: Dict[str, str]) -> Optional[Dict[str, object]]:
    for path in paths:
        for url in _build_urls(path, params):
            try:
                with urllib.request.urlopen(url, timeout=_TIMEOUT) as response:
                    body = response.read().decode("utf-8")
                    data = json.loads(body)
                    if isinstance(data, dict) and not data.get("error"):
                        return data
            except urllib.error.HTTPError:
                continue
            except Exception:
                continue
    return None


def _post_json(paths: Iterable[str], payload: Dict[str, object]) -> Optional[Union[JsonDict, JsonList]]:
    token = _load_api_key()
    if not token:
        return None

    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for path in paths:
        normalized_path = path if path.startswith("/") else f"/{path}"
        for base_url in _base_candidates():
            url = f"{base_url.rstrip('/')}{normalized_path}"
            request = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    if isinstance(data, dict) and not data.get("error"):
                        return data
                    if isinstance(data, list) and data:
                        return data
            except urllib.error.HTTPError:
                continue
            except Exception:
                continue
    return None


def fetch_company_info(domain: Optional[str] = None) -> Optional[Dict[str, object]]:
    """Return core company fields supplied by the Company Enrichment API."""

    if not domain:
        return None

    data = _post_json(_ENRICH_POST_PATHS, {"domain": domain}) or _request(
        _ENRICH_PATH_CANDIDATES, {"domain": domain}
    )
    if not isinstance(data, dict):
        return None

    payload = data.get("company") if isinstance(data.get("company"), dict) else data
    if not isinstance(payload, dict):
        return None

    industry_values = _extract_industries(payload)

    return {
        "domain": payload.get("domain") or domain,
        "name": payload.get("name"),
        "description": payload.get("description") or payload.get("headline"),
        "employees": payload.get("employees") or payload.get("employees_count"),
        "industry": payload.get("industry"),
        "country": payload.get("country"),
        "funding": payload.get("funding"),
        "logo": payload.get("logo"),
        "industries": industry_values,
    }


def fetch_similar_companies(domain: Optional[str], limit: int = 5) -> List[Dict[str, object]]:
    """Return a list of lookalike companies for competitor seeding."""

    if not domain:
        return []

    raw_data: Optional[Union[JsonDict, JsonList]] = _post_json(_SIMILAR_POST_PATHS, {"domain": domain})
    if raw_data is None:
        raw_data = _request(_SIMILAR_PATH_CANDIDATES, {"domain": domain, "limit": str(limit)})

    companies: List[Dict[str, object]] = []
    if isinstance(raw_data, dict):
        raw_list = (
            raw_data.get("items")
            or raw_data.get("companies")
            or raw_data.get("results")
            or raw_data.get("similar_companies")
            or raw_data.get("data")
        )
        if isinstance(raw_list, list):
            companies = [item for item in raw_list if isinstance(item, dict)]
    elif isinstance(raw_data, list):
        for entry in raw_data:
            if isinstance(entry, dict):
                items = entry.get("items")
                if isinstance(items, list):
                    companies.extend([item for item in items if isinstance(item, dict)])
                else:
                    companies.append(entry)

    normalized: List[Dict[str, object]] = []
    for item in companies:
        if not isinstance(item, dict):
            continue

        candidate_domain = (
            item.get("domain")
            or item.get("company_domain")
            or item.get("website")
            or item.get("company_website")
        )
        name = (
            item.get("name")
            or item.get("company_name")
            or item.get("organization_name")
        )
        industry = (
            item.get("industry")
            or item.get("main_industry")
            or item.get("primary_industry")
        )
        description = (
            item.get("description")
            or item.get("headline")
            or item.get("summary")
        )
        employees = (
            item.get("employees")
            or item.get("employees_count")
            or item.get("employee_count")
        )
        country = item.get("country") or item.get("hq_country")

        normalized.append(
            {
                "domain": candidate_domain if isinstance(candidate_domain, str) else None,
                "name": name,
                "description": description,
                "industry": industry,
                "country": country,
                "employees": employees,
                "funding": item.get("funding"),
                "source": "api",
            }
        )

    normalized = [entry for entry in normalized if entry.get("domain") or entry.get("name")]
    if normalized:
        return normalized[:limit]

    fallback = _fallback_competitors(domain or "")
    return fallback[:limit] if fallback else []


def _fallback_competitors(domain: str) -> List[Dict[str, object]]:
    """Provide static competitor seeds when the API has no coverage."""

    canonical = (domain or "").split(".")[0].lower()
    presets: Dict[str, List[Dict[str, object]]] = {
        "microsoft": [
            {"name": "Google", "domain": "google.com", "industry": "Technology"},
            {"name": "Apple", "domain": "apple.com", "industry": "Technology"},
            {"name": "Amazon", "domain": "amazon.com", "industry": "Technology"},
        ],
        "google": [
            {"name": "Microsoft", "domain": "microsoft.com", "industry": "Technology"},
            {"name": "AWS", "domain": "aws.amazon.com", "industry": "Cloud"},
        ],
        "openai": [
            {"name": "Anthropic", "domain": "anthropic.com", "industry": "AI"},
            {"name": "Cohere", "domain": "cohere.com", "industry": "AI"},
        ],
        "porsche": [
            {"name": "Mercedes-Benz", "domain": "mercedes-benz.com", "industry": "Manufacturing"},
            {"name": "BMW", "domain": "bmw.com", "industry": "Manufacturing"},
            {"name": "Audi", "domain": "audi.com", "industry": "Manufacturing"},
        ],
        "audi": [
            {"name": "BMW", "domain": "bmw.com", "industry": "Manufacturing"},
            {"name": "Mercedes-Benz", "domain": "mercedes-benz.com", "industry": "Manufacturing"},
            {"name": "Jaguar", "domain": "jaguar.com", "industry": "Manufacturing"},
        ],
        "bmw": [
            {"name": "Mercedes-Benz", "domain": "mercedes-benz.com", "industry": "Manufacturing"},
            {"name": "Audi", "domain": "audi.com", "industry": "Manufacturing"},
            {"name": "Porsche", "domain": "porsche.com", "industry": "Manufacturing"},
        ],
    }
    generic: List[Dict[str, object]] = [
        {"name": "Acme Corp", "domain": "acme.example", "industry": "General"},
        {"name": "Globex", "domain": "globex.example", "industry": "General"},
    ]
    return presets.get(canonical, generic)


def _extract_industries(payload: Dict[str, object]) -> List[str]:
    """Normalize any industry/segment collections in the payload."""

    candidates: List[str] = []

    direct = payload.get("industry")
    if isinstance(direct, str):
        candidates.append(direct)

    list_sources = [
        payload.get("industries"),
        payload.get("industry_tags"),
        payload.get("tags"),
        payload.get("categories"),
    ]
    for source in list_sources:
        if isinstance(source, list):
            for item in source:
                if isinstance(item, str):
                    candidates.append(item)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("value")
                    if isinstance(name, str):
                        candidates.append(name)

    normalized = []
    seen = set()
    for value in candidates:
        clean = value.strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(clean)
    return normalized

