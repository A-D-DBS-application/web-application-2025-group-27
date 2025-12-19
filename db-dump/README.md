# Backups

Database backups in JSON en SQL formaat, gemaakt met `tools/create_backup.py`.

## Gebruik

```bash
python3 tools/create_backup.py
```

Dit maakt automatisch twee bestanden:
- `backup_mvp_YYYYMMDD_HHMMSS.json` - JSON export
- `backup_mvp_YYYYMMDD_HHMMSS.sql` - SQL dump (pg_dump of INSERT statements)

## Inhoud

Backups bevatten alle database tabellen:
- users, companies, competitors, industries, company_industries, snapshots, signals

**Nota:** Backup bestanden worden genegeerd door git (`.gitignore`).

