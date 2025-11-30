# CompanyEnrich API Key Setup

## Stap 1: API Key Verkrijgen

1. Ga naar [CompanyEnrich Dashboard](https://app.companyenrich.com/)
2. Maak een account aan (gratis tier beschikbaar)
3. Log in en ga naar je dashboard
4. Kopieer je API key

## Stap 2: .env Bestand Aanmaken

Maak een `.env` bestand in de project root (naast `config.py`):

```bash
cd Rival
cp .env.example .env
```

## Stap 3: API Key Toevoegen

Open het `.env` bestand en voeg je API key toe:

```bash
# CompanyEnrich API Configuration
COMPANY_ENRICH_API_KEY=je-api-key-hier
```

**Voorbeeld:**
```bash
COMPANY_ENRICH_API_KEY=sk_live_abc123xyz789
```

## Stap 4: Verifiëren

Start de applicatie en test signup met een company domain:

```bash
python3 run.py
```

Ga naar `/signup` en vul een company domain in (bijv. `example.com`). 
Als de API key correct is ingesteld, wordt company data automatisch opgehaald.

## Troubleshooting

### API key werkt niet?

1. **Check of .env bestand bestaat:**
   ```bash
   ls -la .env
   ```

2. **Check of API key correct is:**
   ```bash
   # In Python shell:
   python3
   >>> import os
   >>> from dotenv import load_dotenv
   >>> load_dotenv()
   >>> print(os.getenv("COMPANY_ENRICH_API_KEY"))
   ```

3. **Check API key format:**
   - Moet beginnen met `sk_` of `sk_live_`
   - Geen spaties aan het begin/einde
   - Volledige key is nodig

4. **Test API direct:**
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        "https://api.companyenrich.com/enrich?domain=example.com"
   ```

### Signup werkt zonder API key?

Dat is normaal! De applicatie werkt ook zonder API key. 
Zonder API key moet je company data handmatig invullen.

### Waar vind ik mijn API key?

- Log in op [CompanyEnrich Dashboard](https://app.companyenrich.com/)
- Ga naar "API Keys" of "Settings"
- Kopieer je API key

## Veiligheid

⚠️ **Belangrijk:**
- Voeg `.env` toe aan `.gitignore` (staat er al in)
- Deel je API key NOOIT publiekelijk
- Gebruik verschillende keys voor development en production

## Gratis Tier

CompanyEnrich heeft een gratis tier met beperkte requests per maand.
Check de [pricing pagina](https://companyenrich.com/pricing) voor details.

