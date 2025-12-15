Rival
=====

## Beschrijving

Rival is een lichtgewicht competitive intelligence MVP gebouwd met Flask.  
De applicatie helpt bedrijven hun concurrenten te volgen via gestructureerde profielen, snapshots en automatische signals.  

## Doel van de MVP

- Aantonen dat AI concurrentie-informatie kan structureren en samenvatten.
- Tonen hoe snapshots en diffs gebruikt kunnen worden om veranderingen bij concurrenten op te volgen.
- Gericht op studenten/docenten en early-stage founders die een eerste zicht op hun competitief landschap willen.

## Kernfunctionaliteiten

- Company tracking: basisprofiel voor het eigen bedrijf en gekoppelde concurrenten.
- Competitor snapshots: gestructureerde “foto’s” met basic, organisatie, hiring focus en strategie.
- Diff + signals: bij betekenisvolle verschillen tussen snapshots worden automatische signals gemaakt.
- Competitive landscape: korte AI-gegenereerde samenvatting van markt en positie.
- Dashboard: één overzichtsscherm met bedrijf, concurrenten, signals en recent nieuws.

## Architectuur (hoog niveau)

- Flask-applicatie met blueprints in `routes/` voor authenticatie, dashboard en detailpagina’s.
- Services in `services/` voor:
  - OpenAI-calls (via `openai_helpers`),
  - company-data (`company_api`),
  - snapshots en signals (`signals`),
  - competitive landscape (`competitive_landscape`).
- PostgreSQL-database met SQLAlchemy:
  - `company`, `company_competitor`, `company_snapshot`, `company_signal` als kernmodellen.

## Algorithmische component

- Snapshots: elke competitor krijgt een JSON-structuur met basic-, organisatie-, hiring- en strategische gegevens.
- Diff-berekening: oude en nieuwe snapshots worden vergeleken; alleen vooraf gedefinieerde “meaningful keys” leiden tot een diff.
- Signals: uit de diff worden gestructureerde signals afgeleid (type, categorie, boodschap, details); optioneel aangevuld met nieuws via web search.

## Installatie en gebruik (lokaal)

1. Repository clonen en map openen:

   ```bash
   git clone https://github.com/your-username/rival.git
   cd rival
   ```

2. Virtuele omgeving en dependencies:

   ```bash
   python -m venv env
   source env/bin/activate  # Windows: env\Scripts\activate
   pip install -r requirements.txt
   ```

3. Omgevingsvariabelen instellen (`.env`):

   ```env
   DATABASE_URL=postgresql://user:password@host:port/database
   SECRET_KEY=een-sterke-geheime-sleutel
   OPENAI_API_KEY=je-openai-sleutel
   ```

4. Database migreren en server starten:

   ```bash
   export FLASK_APP="app:create_app"
   flask db upgrade
   python run.py
   ```

De applicatie is dan bereikbaar op `http://localhost:5000`.

## Externe links

- **UI prototype**  
  Zie de map `images/ui-prototype/` voor statische screenshots van de belangrijkste schermen.  
  Een tijdelijk live prototype kan indien nodig via Lovable gedeeld worden.

- **Kanban board**  
  Miro-bord voor sprint- en takenopvolging:  
  `https://miro.com/app/board/uXjVJwMn8m4=/`

- **Feedbackopnames**  
  Sprint 1 feedbacksessies (StarApps – Jeroen Vroman) in `docs/sprints/first/`:
  - `Session_1.mp4`
  - `Session_2.mp4`