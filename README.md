## Startup Intelligence Platform – Backend Overview

This repository hosts a Flask + SQLAlchemy backend that powers the startup
intelligence platform.  It integrates with Supabase (PostgreSQL) and ingests
company data from Clay so we can map competitive landscapes, generate weekly
reports, and later trigger change notifications (watchdog).

### Key Components

- `app.py` – Flask application factory and SQLAlchemy initialization.
- `models.py` – ORM models aligned with the Supabase schema.  All primary keys
  are UUIDs, companies/competitors are linked through bridge tables, and key
  entities track `last_updated` + `source` metadata for reporting/watchdog.
- `services/` – Service layer encapsulating Clay ingestion, reporting, and
  watchdog logic.
- `routes.py` – JSON-based API endpoints for syncing data, reading companies,
  generating reports, and running watchdog checks.

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
2. Export the Supabase connection string (optional – defaults to the URI in
   `config.py`):
   ```bash
   set FLASK_APP=run.py
   set DATABASE_URL=postgresql://...
   ```
3. Create/upgrade the schema (after model changes):
   ```bash
   flask db migrate -m "sync models"
   flask db upgrade
   ```
4. Start the dev server:
   ```bash
   python run.py
   ```

### API Surface

| Method | Path                          | Description                                      |
|--------|------------------------------|--------------------------------------------------|
| GET    | `/health`                     | Health probe                                     |
| GET    | `/companies`                  | List all companies with competitors/industries   |
| GET    | `/companies/<uuid>`           | Company details                                  |
| GET    | `/companies/<uuid>/report`    | Weekly report payload for a company              |
| GET    | `/reports/companies`          | Reports for every company                        |
| POST   | `/sync/company`               | Trigger Clay sync (requires identifier/snapshot) |
| POST   | `/watchdog/company`           | Compare stored data vs latest Clay snapshot      |
| GET    | `/profiles/<uuid>`            | Retrieve a profile with account/company links    |

All routes return JSON responses.  `POST /sync/company` currently calls a
placeholder Clay client – provide `snapshot` data in the request body until the
real API connector is implemented.

### Clay Integration

`services/clay.py` defines a `ClayClient` stub.  Replace `fetch_company_bundle`
with an actual HTTP client that:

1. Authenticates with Clay.
2. Fetches company, competitor, industry, and product data.
3. Returns a normalized dictionary matching the contract documented in the
   docstring.

`ClaySyncService` consumes this payload and persists the graph into Supabase,
upserting companies, industries, competitors, and products while tracking
metadata.

### Reporting & Watchdog

- `ReportingService` aggregates company, profile, competitor, industry, and
  product information into a weekly report payload.  Hook this into your email
  scheduler to send one report per company.
- `WatchdogService` compares a new Clay snapshot with the stored record and
  produces a diff structure.  Extend it to trigger notifications (email, Slack,
  etc.) when key metrics change.

### Next Steps / TODO

- Implement the real Clay API calls in `ClayClient`.
- Wire an async or scheduled job that runs `ClaySyncService` weekly.
- Schedule `ReportingService.generate_all_company_reports()` to feed the email
  pipeline.
- Extend `WatchdogService` to inspect competitor/industry collections and
  dispatch alerts.
- Add Alembic migrations reflecting the new UUID schema (run `flask db migrate`
  after pulling these changes).

Questions? Ping the backend squad in Slack.  The service layer and routes are
designed to stay stable while we evolve the Supabase schema and automation.