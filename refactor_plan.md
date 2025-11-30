# Refactor Plan for MVP: Config, API Docstring, Competitor Algorithm & Small Trims

You are working in a small Flask MVP project.  
Follow the steps below **in order** and apply them across the entire project folder.

**Very important constraints:**

- ❌ Do NOT change the database schema (models and relationships must stay exactly as they are).
- ❌ Do NOT remove core functionality:
  - signup → user + company
  - CompanyEnrich API enrichment
  - competitor fetching & linking
  - dashboard + company/competitor detail pages
- ✅ You MAY simplify logic, remove unused code, and clean up configuration.

---

## STEP 1 — Clean Up Database URL Handling in `config.py`

### Goal

Make the database configuration safer and clearer:

- Prefer environment variable `DATABASE_URL`.
- Avoid hard-coding a real Supabase URL as a default.
- If `DATABASE_URL` is missing, it should fail clearly or use a harmless local dev default.

### Instructions

1. Open `config.py`.
2. Locate the `Config` class and the `SQLALCHEMY_DATABASE_URI` line.

3. Replace the fallback Supabase URL with either:

**Option A – Strict (requires DATABASE_URL)**  
```
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is required.")
    SQLALCHEMY_DATABASE_URI = db_url
```

**Option B – Local default for development**  
```
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/postgres",
    )
```

4. Ensure the real Supabase URL is NOT hardcoded.

---

## STEP 2 — Fix & Clarify the `fetch_company_info` Docstring

### Goal

Explain correctly what the function returns:
- `None` if the domain is invalid,
- otherwise a dict (sometimes mostly empty).

### Updated Docstring Example

```
def fetch_company_info(domain: Optional[str]) -> Optional[Dict[str, Any]]:
    '''
    Fetch company data from the CompanyEnrich API.

    Returns:
        - None if the domain is missing or invalid.
        - A dict with normalized company data if API succeeds.
        - A dict with mostly None values if API fails (via _empty_api_response).

    This dict should be passed to `apply_company_data` and
    `link_company_industries`.
    '''
```

---

## STEP 3 — Add a Simple Competitor Ranking Algorithm  
⚠️ **This algorithm MUST be placed in: `Rival/services/algorithm.py`**

### Goal

Compute a simple similarity score between your company and each competitor based on employee count.

### Implementation

Create a new file:

```
Rival/services/algorithm.py
```

with:

```
def compute_employee_similarity(base_employees, competitor_employees):
    '''
    Lower score = more similar.
    Returns None if score cannot be computed.
    '''
    if not base_employees or not competitor_employees:
        return None
    try:
        return abs(int(base_employees) - int(competitor_employees))
    except (TypeError, ValueError):
        return None
```

### Integrate in `routes/main.py`

1. Import the algorithm:

```
from Rival.services.algorithm import compute_employee_similarity
```

2. Build competitor view models:

```
competitor_view_models = []
for link in company.competitors:
    competitor = link.competitor
    score = compute_employee_similarity(
        company.number_of_employees,
        competitor.number_of_employees
    )
    competitor_view_models.append({
        "company": competitor,
        "link": link,
        "similarity_score": score,
    })
```

3. Sort them:

```
competitor_view_models.sort(
    key=lambda x: (x["similarity_score"] is None, x["similarity_score"])
)
```

4. Pass to template:

```
return render_template(
    "index.html",
    company=company,
    competitor_view_models=competitor_view_models,
    metrics=metrics,
    team_members=team_members,
)
```

---

## STEP 4 — Safe Code Trims

### 4.1 API parsing cleanup

In `services/company_api.py`, remove any parsing or fields that:

- are never used,
- are complex but add no MVP value (financial metadata, stock data, etc.).

Keep only:
- name  
- domain  
- website  
- description/headline  
- industry / industries  
- number_of_employees  
- funding (if used)  
- country  
- updated_at  

### 4.2 Remove all dead code

Delete:
- commented-out sections,
- unused helpers,
- unused imports,
- previous experimental logic.

### 4.3 Remove duplicate logic

Where logic repeats across routes or API helpers, simplify it ONLY if:

- it reduces code volume AND  
- does not increase abstraction complexity.

---

## STEP 5 — Final Sanity Check

After applying changes:

- Ensure signup → API → competitor linking still works.
- Ensure dashboard + detail pages render without errors.
- Ensure industry M2M and competitor M2M still function.
- Ensure database schema remains unchanged.
- Verify no unused fields or unused parsing leftovers remain.
- Verify environment variables are still loaded correctly.

---

If all steps are complete, your MVP project will be:

- simpler  
- more robust  
- more maintainable  
- fully compliant with assignment requirements  
