# Rival

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Rival helps founders, operators and strategy teams understand their market at lightning speed.** With AI-driven monitoring, Rival tracks your competitor field and surfaces key company updates as they happen.

![Landing Page](images/app-screenshots/landing.png)

---

## 📋 Table of Contents

- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Prototype](#-prototype-ui--interface)
- [Installation](#-installation)
- [Documentation](#-documentation)
- [Kanban Board](#-kanban-board)
- [Sprints](#-sprints)
- [Team](#-team)
- [License](#-license)

---

## ✨ Features

- **Company Tracking** — Monitor competitors with detailed company profiles
- **AI-Powered Signals** — Categorized alerts for hiring, product, and funding changes
- **Competitive Landscape** — AI-generated competitive analysis
- **Company Enrichment** — Auto-enrich company data via OpenAI
- **Real-time Updates** — Stay informed with the latest market movements

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.10+, Flask 3.1 |
| **Database** | PostgreSQL (Supabase compatible) |
| **ORM** | SQLAlchemy, Flask-Migrate (Alembic) |
| **Frontend** | Jinja2 Templates, Tailwind CSS |
| **AI** | OpenAI API |
| **Data Enrichment** | CompanyEnrich API |

---

## 🎨 Prototype (UI / Interface)

**Live preview (valid for 7 days):**  
[View Prototype on Lovable](https://id-preview--16083f01-3507-479c-aa76-f1d19ec41eb4.lovable.app/?__lovable_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiQWNZdU9wZWJ2ZVFzY0RMYm5Xb2llRkQ4cnNEMiIsInByb2plY3RfaWQiOiIxNjA4M2YwMS0zNTA3LTQ3OWMtYWE3Ni1mMWQxOWVjNDFlYjQiLCJub25jZSI6ImI4NWFiZWRmOTQ0NzY2ZjFjODNkNzk4YzBhNjcwMjE2IiwiaXNzIjoibG92YWJsZS1hcGkiLCJzdWIiOiIxNjA4M2YwMS0zNTA3LTQ3OWMtYWE3Ni1mMWQxOWVjNDFlYjQiLCJhdWQiOlsibG92YWJsZS1hcHAiXSwiZXhwIjoxNzY1MzAzODUwLCJuYmYiOjE3NjQ2OTkwNTAsImlhdCI6MTc2NDY5OTA1MH0.2RLsZbfeLxXpW2kcQG12vNDMWlbrlgn6Ioto0cs8lO0)

> ⚠️ If the link has expired, replace it with a fresh 7-day share link from Lovable.

<details>
<summary>📸 UI Prototype Screenshots</summary>

See all prototype screenshots in [`images/ui-prototype/`](images/ui-prototype/)

</details>

---

## 📦 Installation

### Prerequisites

- Python 3.10+
- PostgreSQL database (or Supabase account)
- OpenAI API key *(required for AI features)*
- CompanyEnrich API key *(optional, supplementary data)*

### Setup

**1. Clone the repository**

```bash
git clone https://github.com/your-username/rival.git
cd rival
```

**2. Create virtual environment**

```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Configure environment**

```bash
cp .env.example .env
# Edit .env with your actual values
```

Required environment variables:

```env
DATABASE_URL=postgresql://user:password@host:port/database
SECRET_KEY=your-secret-key
OPENAI_API_KEY=your-openai-key          # Required for AI features
COMPANY_ENRICH_API_KEY=your-api-key     # Optional
```

**5. Run database migrations**

```bash
export FLASK_APP="app:create_app"
flask db upgrade
```

**6. Start the server**

```bash
python run.py
```

The app will be available at **[http://localhost:5000](http://localhost:5000)**.

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [API Guide](docs/API_GUIDE.md) | External API integration details |
| [Enrichment & Caching](docs/ENRICHMENT_CACHING.md) | Company data enrichment system |
| [Migration Guide](docs/MIGRATION_GUIDE.md) | Database migration instructions |
| [Signals System](docs/Signals_System/README.md) | Real-time signals architecture |
| [Full Documentation](docs/Final/Rival_Documentation.md) | Complete project documentation |

---

## 🗂 Kanban Board

Track project progress on our Miro board:

🔗 [Miro Kanban Board](https://miro.com/app/board/uXjVJwMn8m4=/)

---

## 🚀 Sprints

### Sprint 1 — Feedback by Jeroen Vroman (StarApps)

| Session | Recording |
|---------|-----------|
| Session 1 | [View Video](docs/sprints/first/Session_1.mp4) |
| Session 2 | [View Video](docs/sprints/first/Session_2.mp4) |

### Sprint 2

*Videos to be added*

---

## 👥 Team

![The Team](images/app-screenshots/the_team.png)

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <sub>Built with ❤️ by the Rival Team</sub>
</p>
