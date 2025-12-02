"""Simple competitor filtering algorithm.

Filters out internal brands, subsidiaries, product names, and same-company domains
from competitor lists returned by the API.
"""

from typing import Dict, List


def extract_root(domain: str) -> str:
    """Extract root domain (second-level domain).
    
    Examples:
        microsoft.com -> microsoft.com
        azure.microsoft.com -> microsoft.com
        www.google.com -> google.com
        
    Args:
        domain: Domain string
        
    Returns:
        Root domain (second-level domain)
    """
    if not domain:
        return ""
    parts = domain.lower().split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain.lower()


def filter_competitors(base_name: str, base_domain: str, competitors: List[Dict]) -> List[Dict]:
    """Filter competitor list to remove internal brands, subsidiaries, and products.
    
    Applies simple deterministic rules to filter out:
    - Companies with same root domain
    - Subdomains/subsidiaries of same company
    - Companies whose name contains base company name
    - Companies whose domain contains base company name
    - Products/services (no employees and no country)
    
    Args:
        base_name: Name of the base company
        base_domain: Domain of the base company
        competitors: List of competitor dictionaries from API
        
    Returns:
        Filtered list of competitor dictionaries
    """
    base_name = (base_name or "").lower().strip()
    base_domain = (base_domain or "").lower().strip()
    base_root = extract_root(base_domain)

    filtered = []
    for comp in competitors:
        comp_name = (comp.get("name") or "").lower().strip()
        comp_domain = (comp.get("domain") or "").lower().strip()
        
        if not comp_domain:
            continue
        
        comp_root = extract_root(comp_domain)

        # Rule 1: same root domain → skip (e.g., microsoft.com and azure.microsoft.com)
        if comp_root and base_root and comp_root == base_root:
            continue

        # Rule 2: subdomain/subsidiary of same company
        # e.g., azure.microsoft.com ends with microsoft.com
        if base_domain and comp_domain.endswith("." + base_domain):
            continue

        # Rule 3: name contains base name (e.g., "Microsoft Azure" contains "Microsoft")
        if base_name and base_name in comp_name:
            continue

        # Rule 4: domain contains base name (e.g., microsoftstore.com contains "microsoft")
        if base_name and base_name in comp_domain:
            continue
        
        # Rule 5: product/service detection (no employees AND no country)
        employees = comp.get("employees")
        country = comp.get("country")
        if "employees" in comp and "country" in comp and not employees and not country:
            continue

        filtered.append(comp)

    return filtered

