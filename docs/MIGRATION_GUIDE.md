# Data Migratie Handleiding

## Overzicht

De migratie `20250101_simplify_to_mvp.py` migreert de database van de oude Account/Profile structuur naar de nieuwe vereenvoudigde MVP structuur.

## Wat doet de migratie?

### Upgrade (vooruit)
1. **Maakt nieuwe `user` tabel aan** - gecombineerde Account/Profile structuur
2. **Migreert data** - kopieert alle data van `account` + `profile` naar `user`
3. **Vereenvoudigt `company` tabel** - verwijdert metadata velden (created_at, last_updated, source, etc.)
4. **Vereenvoudigt `company_competitor`** - verwijdert `relationship_type` veld
5. **Verwijdert ongebruikte tabellen** - `product`, `industries`, `company_industry`
6. **Verwijdert oude tabellen** - `account`, `profile`

### Downgrade (terug)
- Herstelt de oude structuur (met mogelijk verlies van sommige data)

## Stappen om de migratie uit te voeren

### ⚠️ BELANGRIJK: Backup eerst!

**Maak altijd een backup van je database voordat je migreert!**

```bash
# Voor PostgreSQL/Supabase
pg_dump -h your-host -U your-user -d your-database > backup_before_mvp_migration.sql
```

### Stap 1: Controleer huidige migratie status

```bash
cd "/Users/jean/Local Doc/Algoritms-Datastructures/Rival"
flask db current
```

Dit toont de huidige migratie versie.

### Stap 2: Test de migratie (aanbevolen)

Als je een test database hebt:

```bash
# Kopieer naar test database
# Voer migratie uit op test database
flask db upgrade
```

### Stap 3: Voer de migratie uit

```bash
# Upgrade naar nieuwe structuur
flask db upgrade
```

Dit zal:
- De nieuwe `user` tabel aanmaken
- Data migreren van account+profile naar user
- Oude tabellen verwijderen
- Company tabel vereenvoudigen

### Stap 4: Verifieer de migratie

Controleer of alles correct is gemigreerd:

```bash
# Check migratie status
flask db current

# Check of user tabel bestaat en data heeft
# (via database client of Python script)
```

### Stap 5: Test de applicatie

Start de applicatie en test:
- Login functionaliteit
- Signup functionaliteit
- Homepage laadt correct
- Data wordt correct getoond

## Data Migratie Details

### User Tabel Migratie

De migratie voert deze SQL uit:

```sql
INSERT INTO "user" (id, email, first_name, last_name, company_id, role, is_active)
SELECT 
    p.id,
    COALESCE(a.email, p.email) as email,
    p.first_name,
    p.last_name,
    p.company_id,
    p.role,
    COALESCE(a.is_active, true) as is_active
FROM profile p
LEFT JOIN account a ON p.account_id = a.id
WHERE p.id IS NOT NULL
```

**Wat gebeurt er:**
- `id` komt van `profile.id`
- `email` komt van `account.email` (of `profile.email` als fallback)
- `first_name`, `last_name`, `company_id`, `role` komen van `profile`
- `is_active` komt van `account.is_active` (default: true)

**Let op:** 
- `phone_number`, `date_of_birth`, `country` van profile worden **niet** gemigreerd (niet in MVP)
- Als je deze data nodig hebt, pas de migratie aan voordat je hem uitvoert

## Problemen oplossen

### Fout: "relation already exists"
De `user` tabel bestaat al. Controleer of je al een migratie hebt uitgevoerd.

### Fout: "column does not exist"
Een kolom die verwacht wordt bestaat niet. Controleer of alle vorige migraties zijn uitgevoerd:
```bash
flask db upgrade
```

### Data ontbreekt na migratie
- Controleer of de JOIN tussen account en profile correct is
- Check of er profiles zijn zonder account (zou niet moeten voorkomen)
- Check de database logs voor errors

### Rollback nodig?

Als je terug moet naar de oude structuur:

```bash
flask db downgrade
```

**Let op:** Dit kan data verlies veroorzaken als er nieuwe data is toegevoegd na de upgrade.

## Post-Migratie Checklist

- [ ] Backup gemaakt
- [ ] Migratie succesvol uitgevoerd
- [ ] `user` tabel bestaat en heeft data
- [ ] Oude tabellen (`account`, `profile`) zijn verwijderd
- [ ] Ongebruikte tabellen (`product`, `industries`, etc.) zijn verwijderd
- [ ] `company` tabel heeft geen metadata kolommen meer
- [ ] Applicatie start zonder errors
- [ ] Login werkt
- [ ] Signup werkt
- [ ] Homepage toont data correct

## Vragen?

Als er problemen zijn:
1. Check de Flask-Migrate logs
2. Check de database logs
3. Verifieer dat alle dependencies geïnstalleerd zijn
4. Controleer of de database connectie werkt

