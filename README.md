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
- Competitor snapshots: gestructureerde "foto's" met basic, organisatie, hiring focus en strategie.
- Diff + signals: bij betekenisvolle verschillen tussen snapshots worden automatische signals gemaakt.
- Competitive landscape: korte AI-gegenereerde samenvatting van markt en positie.
- Dashboard: één overzichtsscherm met bedrijf, concurrenten, signals en recent nieuws.

## Architectuur (hoog niveau)

- Flask-applicatie met blueprints in `routes/` voor authenticatie, dashboard en detailpagina's.
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
- Signals: uit de diff worden gestructureerde signals afgeleid (type, categorie, boodschap, details).

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

## User Stories

De user stories voor deze MVP zijn gedocumenteerd in een word-bestand.  
[User Stories WORD](https://docs.google.com/document/d/1EGdD-MdDd5ckVSKveEku67NvECo1FRZj/edit?usp=share_link&ouid=117236600471541148202&rtpof=true&sd=true)

## Externe links

- **Live applicatie**  
  De applicatie is live beschikbaar op Render:  
  [Live App](https://rival-2z3l.onrender.com)

- **Demo video**  
  [Demo Video](https://drive.google.com/file/d/1ZqCnuZURTqDIqdoQ94JPraPxbrtz1ZLk/view?usp=sharing)

- **UI prototype**  
  Zie de map `images/ui-prototype/` voor statische screenshots van de belangrijkste schermen.  
  Live prototype: [Lovable Prototype](https://id-preview--16083f01-3507-479c-aa76-f1d19ec41eb4.lovable.app/#industries)  
  [UI Screenshots](images/ui-prototype/)

- **Kanban board**  
  Miro-bord voor sprint- en takenopvolging:  
  `https://miro.com/app/board/uXjVJwMn8m4=/`

- **Database Schema (ERD)**  
  Zie `docs/ERD.md` voor het volledige Entity Relationship Diagram met alle tabellen, relaties en constraints.  
  [ERD Afbeelding](images/database/ERD.png)

- **Agile Process**  
  Sprint planning en feedback is gedocumenteerd via het Miro Kanban board.  
  Partner feedback sessies met StarApps (Jeroen Vroman) zijn uitgevoerd tijdens Sprint 1:
  - [Sprint 2 Feedback Sessie 1](https://drive.google.com/file/d/1zhyswnSrefaYdzM4G6vYLeBp9g-qgQ4n/view?usp=share_link)
  - [Sprint 2 Feedback Sessie 2](https://drive.google.com/file/d/1HsMQHlAAv_ODQGJebyDVyl0ITxNAOx7H/view?usp=sharing)
  - [Sprint 3 Feedback Sessie 3](https://drive.google.com/file/d/11P3shbbTTjRxh4M5L11y_ps1Qwbu29xg/view?usp=sharing)
