# Backups

Database backups in JSON formaat, gemaakt met `tools/create_backup.py`.

## Gebruik

```bash
python3 tools/create_backup.py
```

## Inhoud

Backups bevatten alle database tabellen:
- users, companies, competitors, industries, company_industries, snapshots, signals

**Nota:** Backup bestanden worden genegeerd door git (`.gitignore`).

