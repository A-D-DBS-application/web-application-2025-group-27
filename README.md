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
- `services/competitive_landscape.py` – AI-powered competitive landscape analysis using OpenAI
- `utils/auth.py` – Authentication/session utilities (login, current user/company, decorators)
- `utils/company_helpers.py` – Helper functions for company enrichment and landscape generation

### Database Schema

#### Entity Relationship Diagram

```
┌─────────────┐
│    User     │
├─────────────┤
│ id (PK)     │
│ email       │──┐
│ first_name  │  │
│ last_name   │  │
│ company_id  │──┼──┐
│ role        │  │  │
│ is_active   │  │  │
└─────────────┘  │  │
                 │  │
                 │  │
┌────────────────┴──┴──┐
│      Company         │
├──────────────────────┤
│ id (PK)              │
│ name                 │
│ domain               │
│ website              │
│ headline             │
│ number_of_employees  │
│ funding              │
│ industry (legacy)    │
│ country              │
│ updated_at           │
│ competitive_landscape│
└──────────────────────┘
         │
         ├──────────────────┐
         │                  │
         ▼                  ▼
┌──────────────────┐  ┌──────────────────────┐
│ CompanyIndustry  │  │ CompanyCompetitor    │
├──────────────────┤  ├──────────────────────┤
│ company_id (PK)  │  │ company_id (PK)      │
│ industry_id (PK) │  │ competitor_id (PK)   │
└──────────────────┘  └──────────────────────┘
         │                        │
         ▼                        ▼
┌─────────────┐          ┌─────────────┐
│  Industry   │          │  Company    │
├─────────────┤          │ (competitor)│
│ id (PK)     │          │             │
│ name        │          └─────────────┘
│ description │
└─────────────┘
```

#### Table Definitions

**`user`**
- `id` (UUID, PK) - Unique user identifier
- `email` (VARCHAR(255), UNIQUE, INDEX) - User email address
- `first_name` (VARCHAR(255)) - User's first name
- `last_name` (VARCHAR(255)) - User's last name
- `company_id` (UUID, FK → `company.id`) - Reference to user's company
- `role` (VARCHAR(255)) - User's role (optional)
- `is_active` (BOOLEAN, DEFAULT true) - Whether the user account is active

**`company`**
- `id` (UUID, PK) - Unique company identifier
- `name` (VARCHAR(255), UNIQUE) - Company name
- `domain` (VARCHAR(255), INDEX) - Company domain (e.g., "nike.com")
- `website` (VARCHAR(500)) - Full website URL
- `headline` (TEXT) - Company description/headline
- `number_of_employees` (INTEGER) - Employee count
- `funding` (BIGINT) - Total funding amount in cents
- `industry` (VARCHAR(255)) - Legacy single industry field (kept for compatibility)
- `country` (VARCHAR(255)) - Company country
- `updated_at` (DATETIME) - Last update timestamp from API
- `competitive_landscape` (TEXT) - AI-generated competitive landscape summary

**`industries`**
- `id` (UUID, PK) - Unique industry identifier
- `name` (VARCHAR(255), UNIQUE) - Canonical industry name
- `description` (TEXT) - Industry description (optional)

**`company_industry`** (Many-to-Many Bridge)
- `company_id` (UUID, PK, FK → `company.id`, CASCADE DELETE)
- `industry_id` (UUID, PK, FK → `industries.id`, CASCADE DELETE)
- Composite primary key ensures one company can have multiple industries

**`company_competitor`** (Competitor Relationships)
- `company_id` (UUID, PK, FK → `company.id`, CASCADE DELETE)
- `competitor_id` (UUID, PK, FK → `company.id`, CASCADE DELETE)
- Composite primary key links companies as competitors
- Both IDs reference the `company` table (self-referential relationship)

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
   
   # Optional: OpenAI API (for AI-powered competitive landscape analysis)
   # Get your API key from https://platform.openai.com/api-keys
   OPENAI_API_KEY=your-openai-api-key-here
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

### AI-Powered Competitive Landscape Analysis

The system automatically generates competitive landscape summaries for companies. This feature uses OpenAI's GPT-4o-mini model when an `OPENAI_API_KEY` is configured, or falls back to a default placeholder text when the API is unavailable.

**How it works:**
- When viewing a company detail page (`/company` or `/competitor/<id>`), the system checks if a competitive landscape summary exists
- If not, it automatically generates a 5-7 sentence analytical summary based on:
  - Company description/headline
  - Industry classifications
  - Known competitors
- The generated landscape covers:
  - Market position and competitive pressures
  - Differentiation factors
  - Strategic considerations and risks
- The summary is cached in the `competitive_landscape` field to avoid repeated API calls

**API Configuration:**
- **With OpenAI API key**: Generates AI-powered landscape summaries using GPT-4o-mini
- **Without API key**: Uses a default placeholder text explaining that landscape analysis is being prepared
- **No competitors**: Uses default text when no competitors are available for analysis

**Testing:**
Use the `tools/generate_landscape.py` script to test landscape generation with full logging:
```bash
python tools/generate_landscape.py "Company Name"
```

### Core Algorithm

The core "algorithm" is the CompanyEnrich-based enrichment and competitor discovery logic plus basic dashboard metrics (team size, competitors, industries, funding), combined with AI-powered competitive landscape analysis.

### Next Steps

After MVP validation, consider adding:
- Product tracking
- Industry categorization
- Advanced company analysis algorithms
- Enhanced competitive intelligence features
- Real-time market monitoring
