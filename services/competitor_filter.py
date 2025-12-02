from typing import Dict, List


def extract_root(domain: str) -> str:
    if not domain: return ""
    parts = domain.lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain.lower()


def filter_competitors(base_name: str, base_domain: str, competitors: List[Dict]) -> List[Dict]:
    base_name = (base_name or "").lower().strip()
    base_domain = (base_domain or "").lower().strip()
    base_root = extract_root(base_domain)

    filtered = []
    for comp in competitors:
        comp_name = (comp.get("name") or "").lower().strip()
        comp_domain = (comp.get("domain") or "").lower().strip()
        if not comp_domain: continue
        
        comp_root = extract_root(comp_domain)
        
        # Skip if: same root domain, subdomain of base, name contains base name, domain contains base name
        if comp_root and base_root and comp_root == base_root: continue
        if base_domain and comp_domain.endswith("." + base_domain): continue
        if base_name and base_name in comp_name: continue
        if base_name and base_name in comp_domain: continue
        
        # Skip products/services with no employees AND no country
        if "employees" in comp and "country" in comp and not comp.get("employees") and not comp.get("country"):
            continue

        filtered.append(comp)
    return filtered
