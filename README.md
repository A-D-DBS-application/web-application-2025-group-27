# Rival — Competitive Intelligence & Market Insights Platform

A Flask-based competitive intelligence platform that automatically enriches company data, discovers competitors, and generates AI-powered market insights using OpenAI GPT-4o-mini.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.x-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## 📸 Screenshots

<!-- Add screenshots here -->
| Dashboard | Market Positioning | Hiring Intelligence |
|-----------|-------------------|---------------------|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Market](docs/screenshots/market-positioning.png) | ![Hiring](docs/screenshots/hiring-intelligence.png) |

---

## ✨ Key Features

### Company Intelligence
- **Automatic Company Enrichment** — Fetches company data (employees, funding, industries, country) from CompanyEnrich API
- **Competitor Discovery** — Automatically identifies and tracks similar companies
- **Industry Classification** — Multi-industry tagging with normalized industry database

### AI-Powered Analysis
- **Competitive Landscape** — AI-generated market positioning summaries
- **Market Positioning** — Structured strategic analysis (value proposition, competitive edge, weaknesses)
- **Hiring Intelligence** — AI-inferred hiring focus, department signals, and strategic interpretation
- **Signals & Alerts** — Automated detection of organizational and competitive changes

### Change Detection
- **Snapshot System** — Historical company data snapshots for change tracking
- **Diff Engine** — Compares snapshots to detect meaningful changes
- **Smart Alerts** — AI-generated signals for headcount changes, industry shifts, funding updates

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.10+, Flask 3.x, SQLAlchemy 2.x |
| **Database** | PostgreSQL (via Supabase) |
| **AI** | OpenAI GPT-4o-mini |
| **Frontend** | Jinja2, Tailwind CSS (JIT), Lucide Icons |
| **APIs** | CompanyEnrich API, OpenAI API |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser (UI)                            │
│                    Tailwind CSS + Lucide Icons                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Flask Application                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ routes/      │  │ templates/   │  │ static/              │  │
│  │  auth.py     │  │  base.html   │  │  styles.css          │  │
│  │  main.py     │  │  index.html  │  │  css/                │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Services Layer                           │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────┐   │
│  │ company_api.py │  │ signals.py     │  │ market_         │   │
│  │ (CompanyEnrich)│  │ (Snapshots,    │  │ positioning.py  │   │
│  │                │  │  Diffs, Alerts)│  │ (AI Analysis)   │   │
│  └────────────────┘  └────────────────┘  └─────────────────┘   │
│  ┌────────────────┐  ┌────────────────┐                        │
│  │ competitive_   │  │ competitor_    │                        │
│  │ landscape.py   │  │ filter.py      │                        │
│  └────────────────┘  └────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
┌───────────────────────┐         ┌───────────────────────┐
│   PostgreSQL (Supabase)│         │      OpenAI API       │
│   ┌─────────────────┐ │         │   (GPT-4o-mini)       │
│   │ company         │ │         │                       │
│   │ user            │ │         │  • Competitive        │
│   │ industries      │ │         │    Landscape          │
│   │ company_industry│ │         │  • Market Positioning │
│   │ company_competitor│         │  • Hiring Intelligence│
│   │ company_snapshot│ │         │  • Signal Generation  │
│   │ company_signal  │ │         │                       │
│   │ market_positioning│         └───────────────────────┘
│   └─────────────────┘ │
└───────────────────────┘
```

---

## 📦 Installation

### Prerequisites
- Python 3.10+
- PostgreSQL database (or Supabase account)
- OpenAI API key (optional, for AI features)
- CompanyEnrich API key (optional, for company enrichment)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/rival.git
   cd rival
   ```

2. **Create virtual environment**
   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

5. **Run database migrations**
   ```bash
   export FLASK_APP="app:create_app"
   flask db upgrade
   ```

6. **Start the server**
   ```bash
   python run.py
   ```

   The app will be available at `http://localhost:5000`

---

## ⚙️ Environment Variables

Create a `.env` file in the project root:

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Flask secret key for sessions |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `OPENAI_API_KEY` | No | OpenAI API key for AI features |
| `COMPANY_ENRICH_API_KEY` | No | CompanyEnrich API key for company data |
| `FLASK_ENV` | No | `development` or `production` |

See `.env.example` for a template.

---

## 📁 Project Structure

```
rival/
├── app.py                 # Flask application factory
├── config.py              # Configuration settings
├── models.py              # SQLAlchemy ORM models
├── run.py                 # Development server entry point
├── requirements.txt       # Python dependencies
│
├── routes/                # Flask blueprints
│   ├── auth.py            # Authentication (login, signup, logout)
│   └── main.py            # Main routes (dashboard, company, competitor)
│
├── services/              # Business logic
│   ├── company_api.py     # CompanyEnrich API client
│   ├── competitive_landscape.py  # AI landscape generation
│   ├── competitor_filter.py      # Competitor filtering heuristics
│   ├── market_positioning.py     # AI market positioning
│   └── signals.py         # Snapshots, diffs, and alert generation
│
├── utils/                 # Utility functions
│   ├── auth.py            # Authentication helpers
│   └── company_helpers.py # Company data helpers
│
├── templates/             # Jinja2 templates
│   ├── base.html          # Base layout
│   ├── index.html         # Dashboard
│   ├── company_detail.html
│   ├── login.html
│   ├── signup.html
│   └── ...
│
├── static/                # Static assets
│   ├── styles.css         # Custom CSS
│   └── css/               # Additional stylesheets
│
└── migrations/            # Alembic database migrations
```

---

## 🔒 Security & Privacy

- **Never commit `.env` files** — Contains sensitive API keys
- **Database credentials** — Store only in environment variables
- **API keys** — Use `.env.example` as a template (no real values)
- **Session security** — Flask's secure session handling

---

## 🚀 API Routes

### Public Routes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Landing page (guests) / Dashboard (logged in) |
| GET | `/login` | Login page |
| POST | `/login` | Authenticate user |
| GET | `/signup` | Registration page |
| POST | `/signup` | Create account + company |
| GET | `/about` | About page |

### Authenticated Routes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/company` | Company detail page |
| GET | `/competitor/<id>` | Competitor detail page |
| GET | `/market-positioning` | Market positioning analysis |
| POST | `/refresh-analysis` | Refresh hiring intelligence |
| POST | `/logout` | Log out |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👥 Team

Built by the Rival team

