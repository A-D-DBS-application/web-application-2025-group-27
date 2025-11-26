## Startup Intelligence Platform – Backend Overview

This repository hosts a Flask + SQLAlchemy backend that powers the startup
intelligence platform.  It integrates with Supabase (PostgreSQL) for data
persistence and provides APIs for managing companies, profiles, and user
authentication.

### Key Components

- `app.py` – Flask application factory and SQLAlchemy initialization.
- `models.py` – ORM models aligned with the Supabase schema.  All primary keys
  are UUIDs, companies/competitors are linked through bridge tables, and key
  entities track `last_updated` + `source` metadata for reporting/watchdog.
- `routes.py` – HTML-based routes for viewing companies, profiles, and user
  authentication.
- `services/company_api.py` – Simple API client that fetches company information
  from Abstract API when users sign up.

### Database Schema (simplified)

```
account ──1─┐
            ▼
         profile ──► company ─┬─ products
                              ├─ company_competitor (self-join)
                              └─ company_industry ─► industries
```

All relationships use UUID foreign keys and cascade rules compatible with
Supabase.

### Running Locally

1. Install dependencies (create a virtualenv first if desired):
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables:**
   
   Create a `.env` file in the project root (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```
   
   Then edit `.env` and add your actual values:
   ```bash
   # Required
   SECRET_KEY=your-secret-key-here-change-this-in-production
   
   # Optional - Database (defaults to config.py value if not set)
   # DATABASE_URL=postgresql://user:password@host:port/database
   
   # Optional - Abstract API (for company data enrichment during signup)
   ABSTRACT_API_KEY=your-abstract-api-key-here
   ```
   
   **Important:** 
   - The `.env` file is in `.gitignore` and will not be committed to git
   - Never commit your actual `.env` file with real keys
   - Use `.env.example` as a template for other developers
   
   **Getting an Abstract API Key (optional):**
   - Go to https://www.abstractapi.com
   - Sign up for a free account (includes 100 free requests per month)
   - Navigate to the Company Enrichment API page
   - Get your API key and add it to your `.env` file
   - If no API key is provided, signup will work but won't fetch company data automatically

3. Set Flask app (if not using .env):
   ```bash
   export FLASK_APP=run.py
   ```

4. Create/upgrade the schema (after model changes):
   ```bash
   flask db migrate -m "sync models"
   flask db upgrade
   ```

5. Start the dev server:
   ```bash
   python run.py
   ```

### Routes

| Method | Path                          | Description                                      |
|--------|------------------------------|--------------------------------------------------|
| GET    | `/health`                     | Health probe (returns plain text "OK")            |
| GET    | `/`                           | Homepage dashboard for logged-in users           |
| GET    | `/login`                      | Login page                                       |
| GET    | `/signup`                     | Sign up page                                     |
| POST   | `/logout`                     | Logout (redirects to login)                      |
| GET    | `/companies`                  | Redirects to company overview                     |
| GET    | `/companies/<uuid>`           | Redirects to company overview                     |
| GET    | `/companies/<uuid>/overview`  | Company details page                             |
| GET    | `/profiles/<uuid>`            | Profile details page                             |
| GET    | `/companies/<uuid>/report`    | Not available                                    |
| GET    | `/reports/companies`          | Not available                                    |
| POST   | `/sync/company`               | Not available                                    |
| POST   | `/watchdog/company`           | Not available                                    |

All routes return HTML pages (except `/health` which returns plain text).

### Company Data Enrichment

When a user signs up, the system automatically tries to fetch company information
from Abstract API if an `ABSTRACT_API_KEY` is configured and a company domain is
provided. The API will populate:

- Company domain (if not provided)
- Company name (if not provided)
- Company description/headline
- Number of employees
- Industry information
- Country information
- Funding information (if available)
- Company logo

**Note:** Abstract API requires a company domain to look up companies. If only a
company name is provided during signup, the API call will be skipped.

If no API key is set, signup still works but company data must be entered manually.

### Next Steps / TODO

- Add Alembic migrations reflecting the new UUID schema (run `flask db migrate`
  after pulling these changes).

Questions? Ping the backend squad in Slack.