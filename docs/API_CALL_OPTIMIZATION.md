# API Call Optimalisatie - Edge Cases Documentatie

**Datum:** 2025-01-XX  
**Doel:** Documentatie van edge cases en optimalisatie logica voor CompanyEnrich API calls tijdens signup

---

## 1. Overzicht

Het systeem voorkomt onnodige API calls wanneer meerdere gebruikers van hetzelfde bedrijf inloggen. Dit bespaart API credits en verbetert performance.

---

## 2. API Call Logica

### 2.1 Wanneer wordt de API call WEL gedaan?

De API call wordt **WEL** gedaan als aan één van deze voorwaarden wordt voldaan:

1. **Nieuw bedrijf** - Het bedrijf bestaat nog niet in de database
2. **Geen domain** - Het bedrijf heeft nog geen `domain` veld
3. **Geen API data** - Het bedrijf heeft nog geen `updated_at` timestamp (nooit API data opgehaald)
4. **Ander domain** - Het ingevoerde domain verschilt van het bestaande domain

### 2.2 Wanneer wordt de API call NIET gedaan?

De API call wordt **NIET** gedaan als:
- Het bedrijf al bestaat in de database
- Het bedrijf heeft al een `domain` veld
- Het bedrijf heeft al een `updated_at` timestamp
- Het ingevoerde domain komt overeen met het bestaande domain

---

## 3. Edge Cases

### 3.1 Case 1: Nieuw Bedrijf
**Scenario:** Eerste gebruiker van een bedrijf registreert zich met domain.

**Gedrag:**
- ✅ API call wordt gedaan
- ✅ Company data wordt opgehaald en opgeslagen
- ✅ `updated_at` wordt gezet
- ✅ Industries worden toegevoegd

**Code Check:**
```python
not company.domain  # True voor nieuw bedrijf
```

---

### 3.2 Case 2: Bestaand Bedrijf, Zelfde Domain
**Scenario:** Tweede gebruiker van hetzelfde bedrijf registreert zich met hetzelfde domain.

**Gedrag:**
- ❌ API call wordt **NIET** gedaan
- ✅ Bestaande company data wordt hergebruikt
- ✅ Nieuwe gebruiker wordt gekoppeld aan bestaand bedrijf
- 💰 **Bespaart:** 1 API credit

**Code Check:**
```python
company.domain == company_domain  # True → skip API call
company.updated_at is not None    # True → heeft al data
```

**Voorbeeld:**
- Gebruiker 1: Signup met "apple.com" → API call gedaan
- Gebruiker 2: Signup met "apple.com" → API call overgeslagen ✅

---

### 3.3 Case 3: Bestaand Bedrijf, Ander Domain
**Scenario:** Gebruiker registreert zich voor een bestaand bedrijf maar met een ander domain.

**Gedrag:**
- ✅ API call wordt gedaan
- ✅ Company data wordt bijgewerkt met nieuw domain
- ✅ `updated_at` wordt bijgewerkt
- ⚠️ **Let op:** Dit kan data overschrijven als het een ander bedrijf is

**Code Check:**
```python
company.domain != company_domain  # True → API call nodig
```

**Voorbeeld:**
- Bedrijf: "Apple Inc" met domain "apple.com"
- Nieuwe gebruiker: "Apple Inc" met domain "apple.co.uk"
- → API call wordt gedaan om data bij te werken

---

### 3.4 Case 4: Bestaand Bedrijf, Geen API Data
**Scenario:** Bedrijf bestaat maar heeft nooit API data opgehaald (geen `updated_at`).

**Gedrag:**
- ✅ API call wordt gedaan
- ✅ Company data wordt aangevuld
- ✅ `updated_at` wordt gezet
- ✅ Industries worden toegevoegd

**Code Check:**
```python
not company.updated_at  # True → nooit API data opgehaald
```

**Voorbeeld:**
- Bedrijf aangemaakt zonder domain (handmatig)
- Later: gebruiker voegt domain toe
- → API call wordt gedaan om data op te halen

---

### 3.5 Case 5: Bestaand Bedrijf, Domain maar Geen updated_at
**Scenario:** Bedrijf heeft domain maar geen `updated_at` (incomplete data).

**Gedrag:**
- ✅ API call wordt gedaan
- ✅ Company data wordt aangevuld/geverifieerd
- ✅ `updated_at` wordt gezet
- ✅ Ontbrekende velden worden gevuld

**Code Check:**
```python
company.domain is not None  # True
not company.updated_at      # True → incomplete data
```

---

### 3.6 Case 6: Meerdere Gebruikers, Zelfde Bedrijf
**Scenario:** 10 gebruikers van hetzelfde bedrijf registreren zich achter elkaar.

**Gedrag:**
- ✅ Eerste gebruiker: API call gedaan (1 credit)
- ❌ Gebruikers 2-10: API call overgeslagen
- 💰 **Bespaart:** 9 API credits

**Voorbeeld:**
```
Gebruiker 1: Signup "apple.com" → API call ✅ (1 credit)
Gebruiker 2: Signup "apple.com" → Skip ❌ (0 credits)
Gebruiker 3: Signup "apple.com" → Skip ❌ (0 credits)
...
Gebruiker 10: Signup "apple.com" → Skip ❌ (0 credits)

Totaal: 1 credit i.p.v. 10 credits
```

### 3.7 Case 7: Competitor Detail View (Nieuwe Pagina)
**Scenario:** Gebruiker bekijkt competitor detail pagina.

**Gedrag:**
- ✅ Eerste keer bekijken (geen data): API call gedaan (1 credit)
- ❌ Tweede keer bekijken (data bestaat): API call overgeslagen (0 credits)
- ✅ Zelfde logica als signup: alleen fetch als `updated_at` ontbreekt of data incompleet is

**Voorbeeld:**
```
Eerste view: Competitor heeft geen updated_at → API call ✅ (1 credit)
Tweede view: Competitor heeft updated_at → Skip ❌ (0 credits)
Derde view: Competitor heeft updated_at → Skip ❌ (0 credits)

Totaal: 1 credit i.p.v. 3 credits
```

**Code Check:**
```python
needs_fetch = (
    not competitor.updated_at or  # Never fetched
    not competitor.headline or    # Incomplete data
    not competitor.website        # Missing website
)
```

---

## 4. Data Update Gedrag

### 4.1 Velden die ALTIJD worden bijgewerkt
- `domain` - Altijd bijgewerkt als API het levert (consistency)
- `updated_at` - Altijd bijgewerkt als API het levert (tracks last fetch)

### 4.2 Velden die ALLEEN worden bijgewerkt als leeg
- `website` - Alleen als leeg
- `headline` - Alleen als leeg
- `number_of_employees` - Alleen als leeg
- `funding` - Alleen als leeg
- `country` - Alleen als leeg
- `industry` - Alleen als leeg
- `stock_symbol` - Alleen als leeg
- `stock_exchange` - Alleen als leeg
- `funding_stage` - Alleen als leeg
- `revenue` - Alleen als leeg

**Reden:** Dit zorgt ervoor dat handmatig ingevoerde data niet wordt overschreven.

---

## 5. Industries Gedrag

### 5.1 Industries Toevoegen
- Industries worden alleen toegevoegd tijdens API call
- Bestaande industries worden niet verwijderd
- Nieuwe industries worden toegevoegd (geen duplicaten)

**Voorbeeld:**
- Bedrijf heeft al: "Software", "Manufacturing"
- API levert: "Software", "Electronics", "Media"
- Resultaat: "Software", "Manufacturing", "Electronics", "Media"

---

## 6. Kosten Analyse

### 6.1 Credits per API Endpoint

| Endpoint | Credits per Call | Gebruik |
|----------|-----------------|---------|
| `GET /companies/enrich` | **1 credit** | Company data ophalen (basis) |
| `POST /companies/similar` | **5 credits per company** | Competitors vinden (optioneel) |

### 6.2 Kosten per Nieuwe Company Fetch

#### Basis Scenario (Alleen Company Data) - ❌ Niet gebruikt
```
1 nieuwe company met domain:
├─ GET /companies/enrich?domain=example.com
└─ Kosten: 1 credit

Totaal: 1 credit per nieuwe company
Status: ❌ Niet geïmplementeerd (competitors worden altijd opgehaald)
```

#### Standaard Scenario (Company + Top 5 Competitors) - ✅ AUTOMATISCH
```
1 nieuwe company met domain + 5 competitors:
├─ GET /companies/enrich?domain=example.com     → 1 credit
└─ POST /companies/similar (5 competitors)      → 5 × 5 = 25 credits

Totaal: 26 credits per nieuwe company
Status: ✅ Automatisch geïmplementeerd tijdens signup
```

#### Volledig Scenario (Company + 10 Competitors) - ❌ Niet gebruikt
```
1 nieuwe company met domain + 10 competitors:
├─ GET /companies/enrich?domain=example.com     → 1 credit
└─ POST /companies/similar (10 competitors)     → 5 × 10 = 50 credits

Totaal: 51 credits per nieuwe company
Status: ❌ Niet geïmplementeerd (max 5 competitors)
```

### 6.3 Kosten per Gebruiker (Met Optimalisatie)

#### Eerste Gebruiker van Bedrijf
```
Eerste gebruiker signup met domain:
├─ Company bestaat nog niet
├─ API call wordt gedaan (company data)
├─ Competitors worden opgehaald (max 5)
└─ Kosten: 26 credits (1 + 25)
```

#### Volgende Gebruikers van Zelfde Bedrijf
```
Tweede+ gebruiker signup met zelfde domain:
├─ Company bestaat al
├─ Domain komt overeen
├─ updated_at bestaat
├─ API call wordt overgeslagen
└─ Kosten: 0 credits ✅
```

### 6.4 Maandelijkse Kosten Schatting

#### Scenario A: 100 Nieuwe Bedrijven, 5 Gebruikers per Bedrijf
```
Zonder optimalisatie:
├─ 100 bedrijven × 5 gebruikers = 500 signups
├─ 500 × 1 credit = 500 credits
└─ Kosten: 500 credits

Met optimalisatie:
├─ 100 bedrijven × 1 API call = 100 credits
├─ 400 signups zonder API call = 0 credits
└─ Kosten: 100 credits
└─ Besparing: 400 credits (80%)
```

#### Scenario B: 50 Nieuwe Bedrijven, 10 Gebruikers per Bedrijf
```
Zonder optimalisatie:
├─ 50 bedrijven × 10 gebruikers = 500 signups
├─ 500 × 1 credit = 500 credits
└─ Kosten: 500 credits

Met optimalisatie:
├─ 50 bedrijven × 1 API call = 50 credits
├─ 450 signups zonder API call = 0 credits
└─ Kosten: 50 credits
└─ Besparing: 450 credits (90%)
```

#### Scenario C: 200 Nieuwe Bedrijven, Gemiddeld 3 Gebruikers per Bedrijf
```
Zonder optimalisatie:
├─ 200 bedrijven × 3 gebruikers = 600 signups
├─ 600 × 1 credit = 600 credits
└─ Kosten: 600 credits

Met optimalisatie:
├─ 200 bedrijven × 1 API call = 200 credits
├─ 400 signups zonder API call = 0 credits
└─ Kosten: 200 credits
└─ Besparing: 400 credits (67%)
```

### 6.5 Kosten met Competitors (Optioneel)

#### Scenario: 100 Bedrijven met Top 5 Competitors
```
Zonder optimalisatie:
├─ 100 bedrijven × 5 gebruikers = 500 signups
├─ 500 × (1 + 25) credits = 13,000 credits
└─ Kosten: 13,000 credits

Met optimalisatie:
├─ 100 bedrijven × (1 + 25) credits = 2,600 credits
├─ 400 signups zonder API call = 0 credits
└─ Kosten: 2,600 credits
└─ Besparing: 10,400 credits (80%)
```

**⚠️ Waarschuwing:** Competitors zijn duur! Gebruik spaarzaam.

### 6.6 Kosten Breakdown per Nieuwe Company

#### Minimale Fetch (Alleen Basis Data)
```
Component                    Credits
─────────────────────────────────────
Company Enrichment           1
─────────────────────────────────────
TOTAAL                       1 credit
```

#### Standaard Fetch (Basis + Industries)
```
Component                    Credits
─────────────────────────────────────
Company Enrichment           1
Industries (included)        0 (gratis)
─────────────────────────────────────
TOTAAL                       1 credit
```

#### Volledige Fetch (Basis + Industries + Competitors)
```
Component                    Credits
─────────────────────────────────────
Company Enrichment           1
Industries (included)        0 (gratis)
Competitors (10 stuks)       50 (5 × 10)
─────────────────────────────────────
TOTAAL                       51 credits
```

#### Aanbevolen Fetch (Basis + Industries + Top 5 Competitors)
```
Component                    Credits
─────────────────────────────────────
Company Enrichment           1
Industries (included)        0 (gratis)
Competitors (5 stuks)        25 (5 × 5)
─────────────────────────────────────
TOTAAL                       26 credits
```

### 6.7 ROI Analyse

#### Zonder Optimalisatie
```
100 bedrijven, 5 gebruikers elk:
- API calls: 500
- Credits: 500
- Kosten: $X (afhankelijk van pricing)
```

#### Met Optimalisatie
```
100 bedrijven, 5 gebruikers elk:
- API calls: 100
- Credits: 100
- Kosten: $X/5 (80% besparing)
- ROI: 400% besparing
```

### 6.8 Aanbevelingen

1. **Gebruik optimalisatie altijd** - Bespaart 67-90% credits
2. **Competitors spaarzaam** - Alleen als echt nodig (5 credits per competitor)
3. **Limiteer competitors** - Max 5-10 per company
4. **Monitor credits** - Houd bij hoeveel credits worden gebruikt
5. **Cache waar mogelijk** - Gebruik `updated_at` om te bepalen of refresh nodig is

---

## 7. Troubleshooting

### 7.1 Probleem: API call wordt niet gedaan maar data is verouderd
**Oplossing:** 
- Verwijder `updated_at` van het bedrijf om refresh te forceren
- Of voeg een "Refresh Company Data" functie toe

### 7.2 Probleem: Verkeerde data voor bedrijf
**Oplossing:**
- Check of domain correct is
- Check of bedrijfsnaam overeenkomt
- Verwijder `updated_at` en voer signup opnieuw uit

### 7.3 Probleem: Industries worden niet toegevoegd
**Oplossing:**
- Check of API call is gedaan (`updated_at` is gezet)
- Check of `industries` array in API response zit
- Check database voor `CompanyIndustry` records

---

## 8. Code Referenties

### 8.1 Signup Route
**Bestand:** `routes/auth.py`  
**Functie:** `signup()`  
**Regels:** 90-121

### 8.2 API Data Toepassen
**Bestand:** `services/company_api.py`  
**Functie:** `apply_company_data()`  
**Regels:** 270-337

### 8.3 API Call Logica
**Bestand:** `routes/auth.py`  
**Regels:** 94-100

---

## 9. Best Practices

1. **Gebruik consistent domain** - Zorg dat alle gebruikers van hetzelfde bedrijf hetzelfde domain gebruiken
2. **Check `updated_at`** - Gebruik dit veld om te zien wanneer data voor het laatst is opgehaald
3. **Monitor API credits** - Houd bij hoeveel credits worden gebruikt
4. **Test edge cases** - Test verschillende scenario's voordat je naar productie gaat

---

## 10. Toekomstige Verbeteringen

### 10.1 Data Refresh Mechanisme
- Optionele "Refresh" knop om data opnieuw op te halen
- Automatische refresh na X dagen (bijv. 30 dagen)

### 10.2 Domain Validatie
- Valideer of domain overeenkomt met bedrijfsnaam
- Waarschuwing als domain verschilt

### 10.3 Caching
- Cache API responses lokaal
- Gebruik cache voor snellere response times

---

**Document versie:** 1.0  
**Laatste update:** 2025-01-XX  
**Auteur:** AI Assistant  
**Status:** ✅ Compleet

