## Startup Intelligence Platform – MVP Backend

Simplified Flask MVP for startup intelligence tracking. This is a minimal implementation focusing on core functionality only.

### Key Components

- `app.py` – Flask application factory
- `models.py` – Simplified ORM models (User, Company, CompanyCompetitor)
- `routes/auth.py` – Authentication routes (login, signup, logout)
- `routes/main.py` – Main application routes (homepage, health)
- `services/algorithm.py` – Core algorithm for company analysis
- `services/company_api.py` – CompanyEnrich API client for company data enrichment
- `utils/auth.py` – Authentication utilities

### Database Schema (Simplified)

```
user ──► company ──► company_competitor ──► company
```

- **User**: email, name, company_id, role
- **Company**: name, domain, headline, basic info
- **CompanyCompetitor**: simple competitor relationships

### Running Locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   
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
   
   See `docs/API_SETUP.md` for detailed API key setup instructions.

3. Create/upgrade the schema:
   ```bash
   flask db migrate -m "Initial MVP schema"
   flask db upgrade
   ```

4. Start the dev server:
   ```bash
   python run.py
   ```

### Routes

| Method | Path      | Description                    |
|--------|-----------|--------------------------------|
| GET    | `/health`  | Health check                   |
| GET    | `/`        | Homepage dashboard             |
| GET    | `/login`   | Login page                     |
| POST   | `/login`   | Login (email-based, no password)|
| GET    | `/signup`  | Sign up page                   |
| POST   | `/signup`  | Create account and company     |
| POST   | `/logout`  | Logout                         |

### Authentication

- **Simple email-based login** - no passwords required (MVP requirement)
- Users are linked to companies
- Session-based authentication

### Company Data Enrichment

When a user signs up with a company domain, the system automatically tries to fetch company information from [CompanyEnrich API](https://docs.companyenrich.com/docs/getting-started) if a `COMPANY_ENRICH_API_KEY` is configured.

The API will populate:
- Company domain
- Company description/headline
- Number of employees
- Industry information
- Country information
- Funding information (if available)

**Note:** If no API key is set, signup still works but company data must be entered manually.

### Core Algorithm

The `services/algorithm.py` module contains:
- `analyze_company_position()` - Analyzes company metrics and returns insights
- `find_similar_companies()` - Finds companies in the same industry

### MVP Simplifications

This MVP has been simplified from the original version:
- ✅ Removed Account/Profile separation (now single User model)
- ✅ Removed Product tracking
- ✅ Simplified external API integration (CompanyEnrich - simple implementation)
- ✅ Removed complex sync utilities
- ✅ Removed detail pages (company/profile)
- ✅ Simplified authentication (email only, no passwords)

See `docs/REFACTORING_SUMMARY.md` for detailed changes.

### Next Steps

After MVP validation, consider adding:
- Product tracking
- Industry categorization
- External API integration (optional)
- Detail pages
- Advanced company analysis algorithms
