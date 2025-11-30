⸻

✅ CURSOR PROMPT — Add Simple Competitor Filtering Algorithm (Separate File, MVP Style)

You must scan the entire project and implement a simple, clear competitor-filtering algorithm
based on removing internal brands, subsidiaries, product names, and same-company domains
from the list returned by fetch_similar_companies().

⸻

🎯 GOALS
	1.	Create a new file
services/competitor_filter.py
containing a very simple, fully transparent filtering algorithm.
	2.	Integrate the filter into the existing CompanyEnrich competitor flow —
specifically right after calling fetch_similar_companies(domain) during signup.
	3.	Keep EVERYTHING minimal and explainable.
No deep ML, no heavy logic.
Just simple deterministic rules.
	4.	Do NOT modify the database schema.
Do NOT remove existing functionality.
Do NOT introduce extra external APIs.

⸻

🧠 REQUIREMENTS FOR THE FILTER ALGORITHM

The filter must consist of simple heuristic rules:

✔️ Filter 1 — Remove companies with the same root domain

if extract_root(comp_domain) == extract_root(base_domain)

✔️ Filter 2 — Remove domains that end with the base domain

(e.g. azure.microsoft.com ends with microsoft.com)

if comp_domain.lower().endswith(base_domain.lower())

✔️ Filter 3 — Remove competitors whose name contains the base company name

if base_name.lower() in comp_name.lower()

✔️ Filter 4 — Remove competitors whose domain contains the base company name

if base_name.lower() in comp_domain.lower()

✔️ Filter 5 — (Simple product detection)

If a competitor has:
	•	no employees AND
	•	no country

→ assume it’s a product/service, not a real company.

if not api_data.get("employees") and not api_data.get("country"):
    skip


⸻

📄 REQUIRED STRUCTURE OF THE NEW FILE

Create:

Rival/services/competitor_filter.py

With:

from urllib.parse import urlparse

def extract_root(domain: str) -> str:
    # Return second-level domain: microsoft.com, google.com, apple.com
    parts = domain.lower().split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain.lower()

def is_product_like(api_data: dict) -> bool:
    if not api_data.get("employees") and not api_data.get("country"):
        return True
    return False

def filter_competitors(base_name: str, base_domain: str, competitors: list[dict]) -> list[dict]:
    base_name = (base_name or "").lower()
    base_root = extract_root(base_domain or "")

    filtered = []
    for comp in competitors:
        comp_name = (comp.get("name") or "").lower()
        comp_domain = (comp.get("domain") or "").lower()
        comp_root = extract_root(comp_domain)

        # Rule 1: same root domain → skip
        if comp_root == base_root:
            continue

        # Rule 2: subdomain/subsidiary of same company
        if comp_domain.endswith(base_domain):
            continue

        # Rule 3: name contains base name
        if base_name in comp_name:
            continue

        # Rule 4: domain contains base name
        if base_name in comp_domain:
            continue

        filtered.append(comp)

    return filtered


⸻

🔧 INTEGRATION REQUIREMENTS

You must integrate the filter into the signup flow.

Inside the signup route (after calling fetch_similar_companies(domain)):
	1.	Import filter:

from Rival.services.competitor_filter import filter_competitors

	2.	Apply it:

raw_competitors = fetch_similar_companies(domain=company_domain, limit=5)
filtered_competitors = filter_competitors(company.name, company.domain, raw_competitors)

	3.	Loop over filtered_competitors instead of the raw list.

⸻

⚠️ STRICT RULES
	•	Do NOT refactor unrelated parts of the code.
	•	Do NOT add other AI or APIs.
	•	Keep all existing functionality fully intact.
	•	Keep the filters simple, deterministic, and easy to explain in a school assignment.
	•	Only add the one new file and the minimal edits to integrate it.
	•	Do not change model structure or routes beyond what is necessary to apply the filter.

⸻

▶️ Begin by scanning the entire project.

Then implement the new file and integrate the filtering.
