# CompanyEnrich API Data Analyse voor Supabase

**Datum:** 2025-01-XX  
**Doel:** Analyse van beschikbare data via CompanyEnrich API om Supabase database zo volledig mogelijk te vullen

---

## 1. Overzicht Database Schema

### 1.1 Company Model (huidige velden)
- `id` (UUID, primary key)
- `name` (String, required)
- `domain` (String, indexed)
- `headline` (Text)
- `number_of_employees` (Integer)
- `funding` (BigInteger)
- `industry` (String) - Legacy single industry field
- `country` (String)

### 1.2 Industry Model (many-to-many)
- `id` (UUID, primary key)
- `name` (String, unique, required)
- `description` (Text)

### 1.3 CompanyIndustry (bridge table)
- `company_id` (UUID, FK)
- `industry_id` (UUID, FK)

### 1.4 CompanyCompetitor (competitors)
- `company_id` (UUID, FK)
- `competitor_id` (UUID, FK)
- `notes` (Text)

---

## 2. CompanyEnrich API Response Structuur

### 2.1 Volledige Response (GET /companies/enrich?domain=example.com)

```json
{
  "id": "019223e7-efae-7f5a-88d9-6793aca548ea",
  "name": "Apple",
  "domain": "apple.com",
  "website": "https://apple.com",
  "type": "public",
  "industry": "Manufacturing",
  "industries": [
    "Manufacturing/Computer Equipment & Peripherals",
    "Manufacturing/Electronics",
    "Software",
    "Media & Internet/Data Collection & Internet Portals",
    "Business Services/Custom Software & IT Services"
  ],
  "categories": ["b2c", "e-commerce"],
  "employees": "over-10K",
  "revenue": "over-1b",
  "description": "Apple is a global technology company...",
  "keywords": ["consumer electronics", "smartphones", ...],
  "technologies": ["Akamai", "Atlassian Confluence", ...],
  "subsidiaries": null,
  "founded_year": 1976,
  "naics_codes": ["334111", "334118", ...],
  "location": {
    "country": {"code": "US", "name": "United States", ...},
    "state": {"id": 4845, "name": "California", "code": "CA", ...},
    "city": {"id": 130565, "name": "Cupertino", ...},
    "address": "One Apple Park Way, Cupertino, CA 95014, United States",
    "postal_code": "95014",
    "phone": "1-800-692-7753"
  },
  "financial": {
    "stock_symbol": "NASDAQ:AAPL",
    "stock_exchange": "nasdaq",
    "total_funding": 1000000000,
    "funding_stage": "post_ipo_debt",
    "funding_date": "2025-05-05T00:00:00",
    "funding": [...]
  },
  "socials": {
    "linkedin_url": "https://www.linkedin.com/company/apple",
    "linkedin_id": "162479",
    "twitter_url": "https://twitter.com/apple",
    "facebook_url": "https://facebook.com/apple/",
    ...
  },
  "page_rank": 8.24,
  "logo_url": "https://api.companyenrich.com/companies/logo/...",
  "seo_description": "Apple Inc. is a global technology leader...",
  "updated_at": "2025-11-22T13:12:52.1925Z"
}
```

### 2.2 Similar Companies Endpoint (POST /companies/similar)
- **Kosten:** 5 credits per company returned
- **Max resultaten:** 100 companies per request
- **Gebruik:** Voor het vinden van competitors

---

## 3. Data Mapping Analyse

### 3.1 ✅ DIRECT BESCHIKBAAR (✅ GEÏMPLEMENTEERD)

| Database Veld | API Veld | Type | Status | Opmerkingen |
|---------------|----------|------|--------|-------------|
| `name` | `name` | String | ✅ **GEBRUIKT** | Exact match, automatisch gemapped |
| `domain` | `domain` | String | ✅ **GEBRUIKT** | Exact match, automatisch gemapped |
| `website` | `website` | String | ✅ **GEBRUIKT** | Volledige website URL, automatisch gemapped |
| `headline` | `description` | Text | ✅ **GEBRUIKT** | Automatisch gemapped tijdens signup |
| `number_of_employees` | `employees` | String→Integer | ✅ **GEBRUIKT** | Conversie logica geïmplementeerd ("over-10K" → 10000) |
| `funding` | `financial.total_funding` | Integer | ✅ **GEBRUIKT** | Automatisch gemapped |
| `country` | `location.country.name` | String | ✅ **GEBRUIKT** | Automatisch gemapped |
| `industry` (legacy) | `industry` | String | ✅ **GEBRUIKT** | Primaire industry, automatisch gemapped |
| `stock_symbol` | `financial.stock_symbol` | String | ✅ **GEBRUIKT** | Beursnotering, automatisch gemapped |
| `stock_exchange` | `financial.stock_exchange` | String | ✅ **GEBRUIKT** | Beurs, automatisch gemapped |
| `funding_stage` | `financial.funding_stage` | String | ✅ **GEBRUIKT** | Funding stage, automatisch gemapped |
| `revenue` | `revenue` | String | ✅ **GEBRUIKT** | Revenue range, automatisch gemapped |
| `updated_at` | `updated_at` | DateTime | ✅ **GEBRUIKT** | Laatste update timestamp, automatisch gemapped |

### 3.2 ✅ BESCHIKBAAR VIA MANY-TO-MANY (Industries) - ✅ GEÏMPLEMENTEERD

| Database Veld | API Veld | Type | Status | Opmerkingen |
|---------------|----------|------|--------|-------------|
| `Industry.name` | `industries[]` | Array[String] | ✅ **GEBRUIKT** | Automatisch geparsed en toegevoegd tijdens signup |
| `Industry.description` | N/A | Text | ❌ Niet beschikbaar | Moet handmatig of via andere bron |

**✅ Geïmplementeerd:**
- ✅ Industry records worden automatisch aangemaakt voor elke waarde in `industries[]` array
- ✅ Link via `CompanyIndustry` bridge table wordt automatisch gemaakt
- ✅ Format parsing: "Manufacturing/Computer Equipment & Peripherals" → neemt laatste deel na "/"
- ✅ Geïmplementeerd in `routes/auth.py` signup route

### 3.3 ✅ BESCHIKBAAR VIA COMPETITORS ENDPOINT - ✅ AUTOMATISCH GEÏMPLEMENTEERD

| Database Veld | API Endpoint | Status | Opmerkingen |
|---------------|--------------|--------|-------------|
| `CompanyCompetitor.competitor_id` | POST `/companies/similar` | ✅ **AUTOMATISCH** | Automatisch opgehaald tijdens signup |
| `CompanyCompetitor.notes` | N/A | ❌ Niet beschikbaar | Handmatig invullen |

**✅ Geïmplementeerd:**
- ✅ Functie `fetch_similar_companies(domain, limit=5)` automatisch aangeroepen tijdens signup
- ✅ Max 5 competitors worden automatisch opgehaald voor nieuwe companies
- ✅ Competitor companies worden automatisch aangemaakt in database
- ✅ Competitor links worden automatisch gemaakt via `CompanyCompetitor` bridge table
- ⚠️ **Kosten:** 25 credits per nieuwe company (5 competitors × 5 credits)
- ✅ **Optimalisatie:** Competitors worden alleen opgehaald bij nieuwe company fetch (niet bij bestaande companies)

### 3.4 ❌ NIET BESCHIKBAAR (niet in API response)

| Database Veld | Status | Alternatief |
|---------------|--------|-------------|
| `Industry.description` | ❌ Niet beschikbaar | Handmatig of via andere API |
| `CompanyCompetitor.notes` | ❌ Niet beschikbaar | Handmatig invullen |

---

## 4. Extra Data Beschikbaar (niet in huidige schema)

### 4.1 Basis Informatie
- ✅ `website` - Volledige website URL
- ✅ `type` - Company type (public, private, etc.)
- ✅ `founded_year` - Oprichtingsjaar
- ✅ `logo_url` - Logo URL van CompanyEnrich

### 4.2 Locatie Details
- ✅ `location.state.name` - Staat/provincie
- ✅ `location.city.name` - Stad
- ✅ `location.address` - Volledig adres
- ✅ `location.postal_code` - Postcode
- ✅ `location.phone` - Telefoonnummer

### 4.3 Financiële Data
- ✅ `financial.stock_symbol` - Beursnotering
- ✅ `financial.stock_exchange` - Beurs
- ✅ `financial.funding_stage` - Funding stage
- ✅ `financial.funding[]` - Array van funding rounds
- ✅ `revenue` - Revenue range (string zoals "over-1b")

### 4.4 Categorisatie
- ✅ `categories[]` - Array van categorieën (b2c, e-commerce, etc.)
- ✅ `keywords[]` - Array van keywords
- ✅ `technologies[]` - Array van gebruikte technologieën
- ✅ `naics_codes[]` - NAICS industry codes

### 4.5 Social Media
- ✅ `socials.linkedin_url` - LinkedIn URL
- ✅ `socials.linkedin_id` - LinkedIn ID
- ✅ `socials.twitter_url` - Twitter URL
- ✅ `socials.facebook_url` - Facebook URL
- ✅ `socials.instagram_url` - Instagram URL
- ✅ `socials.crunchbase_url` - Crunchbase URL

### 4.6 Metadata
- ✅ `page_rank` - Google PageRank
- ✅ `seo_description` - SEO beschrijving
- ✅ `updated_at` - Laatste update timestamp
- ✅ `subsidiaries` - Dochterondernemingen (meestal null)

---

## 5. Aanbevelingen voor Database Uitbreiding

### 5.1 Nieuwe Velden voor Company Model

```python
# Aanbevolen nieuwe velden:
website = db.Column(db.String(500))  # Volledige website URL
company_type = db.Column(db.String(50))  # public, private, etc.
founded_year = db.Column(db.Integer)
logo_url = db.Column(db.String(500))
state = db.Column(db.String(255))  # Staat/provincie
city = db.Column(db.String(255))  # Stad
address = db.Column(db.Text)  # Volledig adres
postal_code = db.Column(db.String(50))
phone = db.Column(db.String(50))
stock_symbol = db.Column(db.String(50))  # NASDAQ:AAPL
stock_exchange = db.Column(db.String(50))  # nasdaq
funding_stage = db.Column(db.String(50))  # post_ipo_debt, etc.
revenue = db.Column(db.String(50))  # over-1b, etc.
page_rank = db.Column(db.Float)
linkedin_url = db.Column(db.String(500))
twitter_url = db.Column(db.String(500))
facebook_url = db.Column(db.String(500))
crunchbase_url = db.Column(db.String(500))
```

### 5.2 Nieuwe Tabellen

#### CompanyKeyword (many-to-many)
```python
class CompanyKeyword(db.Model):
    company_id = db.Column(UUID, db.ForeignKey("company.id"), primary_key=True)
    keyword = db.Column(db.String(255), primary_key=True)
```

#### CompanyTechnology (many-to-many)
```python
class CompanyTechnology(db.Model):
    company_id = db.Column(UUID, db.ForeignKey("company.id"), primary_key=True)
    technology = db.Column(db.String(255), primary_key=True)
```

#### CompanyCategory (many-to-many)
```python
class CompanyCategory(db.Model):
    company_id = db.Column(UUID, db.ForeignKey("company.id"), primary_key=True)
    category = db.Column(db.String(255), primary_key=True)
```

#### CompanyNAICS (many-to-many)
```python
class CompanyNAICS(db.Model):
    company_id = db.Column(UUID, db.ForeignKey("company.id"), primary_key=True)
    naics_code = db.Column(db.String(10), primary_key=True)
```

---

## 6. Implementatie Plan

### 6.1 Fase 1: Basis Data (MVP - ✅ GEÏMPLEMENTEERD)
- ✅ `name`, `domain`, `headline`, `number_of_employees`, `funding`, `country`, `industry`
- ✅ Industries (many-to-many via `CompanyIndustry`)

### 6.2 Fase 2: Competitors (✅ GEÏMPLEMENTEERD)
- ✅ Implementeer `/companies/similar` endpoint call (`fetch_similar_companies()`)
- ✅ Functie beschikbaar in `services/company_api.py`
- ✅ **Automatisch geïmplementeerd:** Max 5 competitors worden automatisch opgehaald tijdens signup
- ⚠️ **Kosten:** 5 credits per competitor = 25 credits per nieuwe company (max 5 competitors)
- ✅ **Status:** Automatisch aangeroepen tijdens signup voor nieuwe companies

### 6.3 Fase 3: Extra Company Velden (✅ GEÏMPLEMENTEERD)
- ✅ Voeg nieuwe velden toe aan Company model:
  - ✅ `website` - Volledige website URL
  - ✅ `stock_symbol` - Beursnotering (e.g., "NASDAQ:AAPL")
  - ✅ `stock_exchange` - Beurs (e.g., "nasdaq")
  - ✅ `funding_stage` - Funding stage (e.g., "post_ipo_debt")
  - ✅ `revenue` - Revenue range (e.g., "over-1b")
  - ✅ `updated_at` - Laatste update timestamp van API
- ✅ Update `apply_company_data()` functie om alle velden te mappen
- ✅ Database migratie uitgevoerd (`88caf396b78e_add_financial_data_website_updated_at_`)
- ✅ Industries automatisch toegevoegd tijdens signup via many-to-many relatie

### 6.4 Fase 4: Keywords, Technologies, Categories (❌ NIET GEÏMPLEMENTEERD)
- ❌ Nieuwe many-to-many tabellen
- ❌ Data mapping van API response
- 💡 **Status:** Optioneel voor toekomstige uitbreiding

---

## 7. Kosten Analyse

### 7.1 Credits per API Endpoint

| Endpoint | Credits per Call | Gebruik |
|----------|-----------------|---------|
| `GET /companies/enrich` | **1 credit** | Company data ophalen (basis) |
| `POST /companies/similar` | **5 credits per company** | Competitors vinden (optioneel) |

### 7.2 Kosten per Nieuwe Company Fetch

#### Minimale Fetch (Alleen Basis Data)
```
Component                    Credits
─────────────────────────────────────
Company Enrichment           1
Industries (included)        0 (gratis)
─────────────────────────────────────
TOTAAL                       1 credit per nieuwe company
```

#### Standaard Fetch (Basis + Top 5 Competitors) - ✅ AUTOMATISCH
```
Component                    Credits
─────────────────────────────────────
Company Enrichment           1
Industries (included)        0 (gratis)
Competitors (5 stuks)        25 (5 × 5) ← Automatisch opgehaald
─────────────────────────────────────
TOTAAL                       26 credits per nieuwe company
```

**Status:** ✅ Automatisch geïmplementeerd tijdens signup

#### Volledige Fetch (Basis + 10 Competitors)
```
Component                    Credits
─────────────────────────────────────
Company Enrichment           1
Industries (included)        0 (gratis)
Competitors (10 stuks)       50 (5 × 10)
─────────────────────────────────────
TOTAAL                       51 credits per nieuwe company
```

### 7.3 Kosten per Gebruiker (Met Optimalisatie)

#### Eerste Gebruiker van Bedrijf
- **Kosten:** 1 credit (basis) of 26 credits (met 5 competitors)
- **Reden:** Company bestaat nog niet, API call wordt gedaan

#### Volgende Gebruikers van Zelfde Bedrijf
- **Kosten:** 0 credits ✅
- **Reden:** Company bestaat al, domain komt overeen, API call wordt overgeslagen

### 7.4 Maandelijkse Kosten Schatting

#### Scenario: 100 Nieuwe Bedrijven, 5 Gebruikers per Bedrijf

**Zonder optimalisatie:**
- 100 bedrijven × 5 gebruikers = 500 signups
- 500 × 1 credit = **500 credits**

**Met optimalisatie:**
- 100 bedrijven × 1 API call = **100 credits**
- 400 signups zonder API call = 0 credits
- **Besparing: 400 credits (80%)**

### 7.5 Kosten met Competitors

**⚠️ Waarschuwing:** Competitors zijn duur!

| Competitors | Credits | Totaal (met basis) |
|-------------|---------|-------------------|
| 0 (alleen basis) | 0 | 1 credit |
| 5 (aanbevolen) | 25 | 26 credits |
| 10 | 50 | 51 credits |
| 20 | 100 | 101 credits |
| 100 (max) | 500 | 501 credits |

**Aanbeveling:** 
- Gebruik `/companies/similar` spaarzaam
- Limiteer aantal competitors tot 5-10 per company
- Cache results waar mogelijk
- Gebruik optimalisatie om duplicate calls te voorkomen

---

## 8. Data Conversie Logica

### 8.1 Employees Conversie
```python
def convert_employees(employees_str: str) -> Optional[int]:
    """Converteer employees string naar integer."""
    if not employees_str:
        return None
    
    # Voorbeelden: "over-10K", "1000-5000", "50-100"
    import re
    numbers = re.findall(r'\d+', employees_str.replace(',', ''))
    if numbers:
        # Neem het grootste getal
        max_num = max(int(n) for n in numbers)
        # Als "over-10K", gebruik 10000 als minimum
        if "over" in employees_str.lower() and "k" in employees_str.lower():
            return max_num * 1000
        return max_num
    return None
```

### 8.2 Industries Parsing
```python
def parse_industries(industries: List[str]) -> List[str]:
    """Parse industries array naar individuele industry namen."""
    result = []
    for industry in industries:
        # Format: "Manufacturing/Computer Equipment & Peripherals"
        # Split op "/" en neem laatste deel
        parts = industry.split("/")
        if len(parts) > 1:
            result.append(parts[-1].strip())
        else:
            result.append(industry.strip())
    return result
```

---

## 9. Conclusie

### 9.1 Wat WEL mogelijk is:
- ✅ Alle basis company velden (name, domain, headline, employees, funding, country)
- ✅ Multiple industries via many-to-many relatie
- ✅ Competitors via `/companies/similar` endpoint
- ✅ Veel extra data (website, type, founded_year, location details, financial data, socials, etc.)

### 9.2 Wat NIET mogelijk is:
- ❌ Industry descriptions (moet handmatig of via andere bron)
- ❌ Competitor notes (moet handmatig)
- ❌ Custom data specifiek voor onze use case

### 9.3 Aanbevelingen:
1. **Prioriteit 1:** Implementeer competitors endpoint (met limiet op aantal)
2. **Prioriteit 2:** Voeg extra company velden toe (website, type, founded_year, location)
3. **Prioriteit 3:** Implementeer keywords/technologies/categories many-to-many tabellen
4. **Kostenbewust:** Limiteer competitors tot top 10-20 per company
5. **Caching:** Cache API responses om credits te besparen

---

## 10. Implementatie Status

### ✅ Voltooide Stappen:
1. ✅ Update `services/company_api.py` om alle beschikbare velden te mappen
2. ✅ Implementeer competitors fetching via `/companies/similar` (`fetch_similar_companies()`)
3. ✅ Database migratie voor nieuwe velden (`88caf396b78e_add_financial_data_website_updated_at_`)
4. ✅ Update `apply_company_data()` functie om alle velden te mappen
5. ✅ Industries automatisch toevoegen tijdens signup
6. ✅ Alle financiële data velden toegevoegd en gemapped

### 📊 Data Gebruik Overzicht:

**Automatisch tijdens signup (als domain wordt ingevuld):**
- ✅ Basis: name, domain, website, headline, employees, funding, country, industry
- ✅ Financieel: stock_symbol, stock_exchange, funding_stage, revenue
- ✅ Metadata: updated_at
- ✅ Industries: Meerdere industries via many-to-many relatie
- ✅ Competitors: Max 5 competitors automatisch opgehaald en gekoppeld

**Optimalisatie - API Call Preventie:**
- ✅ **Geïmplementeerd:** API call wordt alleen gedaan als:
  - Bedrijf bestaat nog niet, OF
  - Bedrijf heeft nog geen domain, OF
  - Bedrijf heeft nog geen `updated_at` (nooit API data opgehaald), OF
  - Ingevoerde domain verschilt van bestaande domain
- ✅ Dit voorkomt onnodige API calls wanneer meerdere gebruikers van hetzelfde bedrijf inloggen
- ✅ Bespaart API credits en verbetert performance
- ✅ Competitors worden alleen opgehaald bij nieuwe company fetch (niet bij bestaande companies)
- 📖 **Zie:** [API_CALL_OPTIMIZATION.md](API_CALL_OPTIMIZATION.md) voor volledige edge cases documentatie

### 🔄 Volgende Stappen (Optioneel):
1. ⚠️ Competitors automatisch ophalen tijdens signup (kost veel credits!)
2. ⚠️ UI/route toevoegen om competitors handmatig op te halen
3. ⚠️ Cache mechanisme voor API responses

---

**Document versie:** 1.0  
**Laatste update:** 2025-01-XX  
**Auteur:** AI Assistant  
**Status:** ✅ Compleet

