# Tools - Rival Project

Development tools voor het Rival (Startup Intelligence Platform) project.

## 📋 Overzicht

Deze folder bevat utility scripts en tools voor development, documentatie, en project maintenance.

Alle tools kunnen direct via Python worden uitgevoerd, of via de bijbehorende shell scripts (`.sh`) voor gemakkelijker gebruik.

## 🛠️ Beschikbare Tools

### `create_backup.py`

Maakt een backup van alle database data in JSON formaat. Belangrijk om te runnen voor belangrijke migraties.

**Gebruik:**
```bash
cd Rival
python3 tools/create_backup.py
```

**Wat doet het?**
- Exporteert alle users, companies en competitor relaties naar JSON
- Backup wordt opgeslagen in project root als `backup_mvp_YYYYMMDD_HHMMSS.json`
- Bevat alle essentiële data voor restore indien nodig

**Output:**
- JSON bestand met timestamp in de naam
- Bevat: users, companies, competitors data

---

### `clear_database.py`

⚠️ **GEVAARLIJK**: Verwijdert alle data uit de database. Alleen voor testdoeleinden!

**Gebruik:**
```bash
cd Rival
# Interactive mode (vraagt om bevestiging)
python3 tools/clear_database.py

# Auto-confirm (gevaarlijk!)
python3 tools/clear_database.py --yes

# Maak eerst backup, dan leegmaken
python3 tools/clear_database.py --backup
```

**Wat doet het?**
- Verwijdert alle data uit alle tabellen
- Behoudt tabel structuur (tabellen blijven bestaan)
- Vereist bevestiging (tenzij `--yes` gebruikt)
- Optioneel: maakt backup voor het leegmaken

**Waarschuwing:**
- ⚠️ Deze actie kan NIET ongedaan worden gemaakt!
- Gebruik alleen in development/test omgevingen
- Maak altijd een backup als je belangrijke data hebt

---

### `test_migration.py`

Verifieert of een database migratie succesvol is uitgevoerd.

**Gebruik:**
```bash
cd Rival
python3 tools/test_migration.py
```

**Wat doet het?**
- Controleert of nieuwe tabellen bestaan en data bevatten
- Verifieert dat oude tabellen correct zijn verwijderd
- Checkt of metadata kolommen zijn verwijderd
- Toont sample data voor verificatie

**Output:**
- ✅ Success checks
- ⚠️ Warnings voor problemen
- ❌ Errors indien iets mis is

---

### `convert_to_markdown.py` / `convert_to_markdown.sh`

Converteert alle Python source bestanden automatisch naar Markdown documentatie met syntax highlighting.

**Gebruik:**

**Optie 1: Via shell script (aanbevolen)**
```bash
cd Rival
bash tools/convert_to_markdown.sh
# of
./tools/convert_to_markdown.sh
```

**Optie 2: Direct Python**
```bash
cd Rival
python3 tools/convert_to_markdown.py
```

**Wat doet het?**
- Scant de project root directory recursief
- Converteert alle `.py` bestanden naar `.md` met code highlighting
- Behoudt directory structuur (services/, migrations/, etc.)
- Sluit automatisch uit: `__init__.py`, `run.py`, `env/`, `migrations/`, etc.

**Output:**
- Markdown bestanden worden opgeslagen in `tools/md/`
- Structuur wordt behouden: `services/company_api.py` → `tools/md/services/company_api.md`

**Configuratie:**

Pas de CONFIGURATION sectie aan in `convert_to_markdown.py`:

```python
# Bestanden die worden uitgesloten
EXCLUDED_FILES: Set[str] = {
    '__init__.py',
    'convert_to_markdown.py',
    'run.py',
    # Voeg toe wat je wilt uitsluiten
}

# Directories die worden uitgesloten
EXCLUDED_DIRS: Set[str] = {
    'md',
    '__pycache__',
    'env',
    'migrations',  # Comment uit als je migrations wel wilt documenteren
    # Voeg toe wat je wilt uitsluiten
}
```

## 📁 Project Structuur

```
Rival/
├── app.py              # Flask app factory
├── models.py           # Database models
├── routes.py           # HTTP routes
├── services/           # Service layer
├── migrations/         # Database migrations
├── tools/              # ← Je bent hier
│   ├── convert_to_markdown.py
│   ├── README.md
│   └── md/             # Output directory (auto-generated)
└── templates/          # Jinja2 templates
```

## 🎯 Toekomstige Tools

Ideeën voor aanvullende tools:

- **Database schema exporter** - Exporteer SQLAlchemy models naar SQL/ER diagram
- **Route documentatie generator** - Genereer API documentatie uit Flask routes
- **Environment setup checker** - Verifieer dat alle benodigde environment variables zijn ingesteld
- **Test coverage reporter** - Genereer coverage reports in markdown format

## 💡 Tips

- Voeg `tools/md/` toe aan `.gitignore` als je de markdown output niet wilt committen
- Gebruik de markdown bestanden voor code reviews en documentatie websites
- Perfect voor archivering en onboarding nieuwe developers

## 📝 Nieuwe Tool Toevoegen

1. Maak een nieuw Python bestand in deze folder
2. Gebruik `TEMPLATE.py` als startpunt (indien beschikbaar)
3. Voeg documentatie toe aan deze README
4. Test de tool en voeg eventuele dependencies toe aan `requirements.txt` als nodig

