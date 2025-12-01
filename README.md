## Rival – Startup Intelligence MVP Backend

Simplified Flask MVP for startup intelligence tracking. This implementation focuses on the core flow: sign up with a startup, enrich the company with external data, and explore basic competitor insights.

**Team planning board (Miro)**:  
`https://miro.com/app/board/uXjVJwMn8m4=/`

### Key Components

- `app.py` – Flask application factory (`create_app`) and database setup
- `models.py` – ORM models: `User`, `Company`, `Industry`, `CompanyIndustry`, `CompanyCompetitor`
- `routes/auth.py` – Authentication routes (login, signup, logout + company & competitor bootstrap)
- `routes/main.py` – Main application routes (dashboard, company detail, competitor detail, health)
- `services/company_api.py` – CompanyEnrich API client for company enrichment & competitor discovery
- `services/competitor_filter.py` – Heuristics to clean/filter competitors from the API
- `services/algorithm.py` – Placeholder for future analysis algorithms
- `utils/auth.py` – Authentication/session utilities (login, current user/company, decorators)

### Database Schema (Simplified)

High‑level relationships:

```
user ──► company ──► company_competitor ──► company
             └────► company_industry ──► industries
```

- **User**: email, first/last name, company_id, role, is_active
- **Company**: name, domain, website, headline, number_of_employees, funding, industry, country, updated_at
- **Industry**: canonical industry names
- **CompanyIndustry**: many‑to‑many bridge between companies and industries
- **CompanyCompetitor**: simple competitor relationships between companies

### Running Locally

1. (Recommended) Use a virtual environment:
   ```bash
   cd Rival
   source env/bin/activate  # or: python -m venv .venv && source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   
   **Option A: Copy example file (recommended)**
   ```bash
   cp .env.example .env
   # Then edit .env and add your values
   ```
   
   **Option B: Create .env manually**
   ```bash
   # Create .env file with:
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=postgresql://user:password@host:port/database
   
   # Optional: CompanyEnrich API (for automatic company data enrichment)
   # Get your API key from https://app.companyenrich.com/
   COMPANY_ENRICH_API_KEY=your-companyenrich-api-key-here
   ```
   
   See `docs/API_SETUP.md` for detailed API key setup instructions and `docs/CREDITS_CALCULATION.md` for API credit usage.

4. Create/upgrade the schema:
   From the project root (`Rival/`), ensure Flask knows how to load the app factory, then run migrations:
   ```bash
   export FLASK_APP="app:create_app"  # or on Windows: set FLASK_APP=app:create_app
   flask db upgrade                   # applies existing migrations
   # Only run migrate when you have changed models:
   # flask db migrate -m "Describe your schema change"
   ```

5. Start the dev server:
   ```bash
   python run.py
   ```

### Routes

Public:

| Method | Path        | Description                               |
|--------|-------------|-------------------------------------------|
| GET    | `/login`    | Login page                                |
| POST   | `/login`    | Login (email-based, no password)         |
| GET    | `/signup`   | Sign up page                              |
| POST   | `/signup`   | Create account and company                |

Authenticated:

| Method | Path                 | Description                               |
|--------|----------------------|-------------------------------------------|
| GET    | `/`                  | Homepage dashboard for current company    |
| GET    | `/company`           | Detail page for the current company       |
| GET    | `/competitor/<id>`   | Detail page for a competitor              |
| POST   | `/logout`            | Logout                                    |
| GET    | `/health`            | Health check                              |

### Authentication

- **Simple email-based login** – no passwords required (MVP requirement)
- Users are linked to companies (one company per user)
- Session-based authentication with a lightweight auth helper

### Company Data Enrichment

When a user signs up with a company domain, the system automatically tries to fetch company information from [CompanyEnrich API](https://docs.companyenrich.com/docs/getting-started) if a `COMPANY_ENRICH_API_KEY` is configured.

The enrichment flow:
- **Company enrichment**: basic company data (name, domain, website, headline, employees, funding, country, industries, updated_at)
- **Industry mapping**: industries from the API are normalized and linked via `Industry` / `CompanyIndustry`
- **Competitors (optional but enabled)**: similar companies are fetched via the `/companies/similar` endpoint and stored in `CompanyCompetitor`

See:
- `docs/COMPANY_ENRICH_DATA_ANALYSIS.md` – detailed mapping of API → database
- `docs/CREDITS_CALCULATION.md` – credit usage and cost breakdown
- `docs/API_CALL_OPTIMIZATION.md` – when calls are skipped to save credits

**Note:**  
- If no API key is set, signup still works, but company data must be entered manually and no competitors are fetched.  
- API calls are only made when needed (new company or stale/missing data) to reduce credit usage.

### Core Algorithm

The `services/algorithm.py` module is reserved for future algorithm implementations.  
For now, the “algorithm” is mainly the CompanyEnrich-based enrichment and competitor discovery logic plus basic dashboard metrics (team size, competitors, industries, funding).

### Next Steps

After MVP validation, consider adding:
- Product tracking
- Industry categorization
- External API integration (optional)
- Detail pages
- Advanced company analysis algorithms
