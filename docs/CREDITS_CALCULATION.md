# Credits Berekening

**Datum:** 2025-01-XX  
**Status:** ✅ Volledig geoptimaliseerd

---

## 1. API Endpoints en Kosten

| Endpoint | Credits per Call |
|----------|------------------|
| `GET /companies/enrich` | **1 credit** |
| `POST /companies/similar` | **5 credits per company** |

---

## 2. Credits per Klik Actie

### 2.1 Signup (Nieuwe Gebruiker)

#### Eerste Gebruiker van Nieuw Bedrijf
```
Company enrich API call          → 1 credit
Competitors fetch (max 5)        → 25 credits (5 × 5)
─────────────────────────────────────────────
TOTAAL: 26 credits
```

#### Volgende Gebruikers van Bestaand Bedrijf
```
Company enrich API call          → 0 credits (skip) ✅
Competitors fetch                → 0 credits (skip) ✅
─────────────────────────────────────────────
TOTAAL: 0 credits ✅
```

**Optimalisatie:** API call alleen als bedrijf nog geen `domain` of `updated_at` heeft.

---

### 2.2 Company Detail View (Eigen Bedrijf)

#### Normaal (Na Signup)
```
Company enrich API call          → 0 credits (skip) ✅
(Data bestaat al na signup, API call wordt overgeslagen)
```

#### Alleen Als Data Ontbreekt (Edge Case)
```
Company enrich API call          → 1 credit
(Alleen als signup zonder domain was, of data incompleet)
```

**Optimalisatie:** Na signup bestaat data al, dus bijna altijd 0 credits.

---

### 2.3 Competitor Detail View

#### Als Data Ontbreekt
```
Company enrich API call          → 1 credit
(Alleen als updated_at, headline of website ontbreekt)
```

#### Als Data Al Bestaat
```
Company enrich API call          → 0 credits (skip) ✅
(Als updated_at bestaat en data compleet is)
```

**Optimalisatie:** API call alleen als data incompleet is.

---

## 3. Kosten Breakdown

### Per Nieuwe Company (Eerste Gebruiker)
```
Component                    Credits
─────────────────────────────────────
Company Enrichment           1
Competitors (max 5)          25
─────────────────────────────────────
TOTAAL                       26 credits
```

### Per Volgende Actie (Data Bestaat Al)
```
Volgende gebruiker signup        → 0 credits ✅
Company detail view (na signup)  → 0 credits ✅ (data bestaat al na signup)
Competitor detail view (data bestaat) → 0 credits ✅
```

**Let op:** 
- Company detail view haalt GEEN competitors op (alleen tijdens signup)
- Company detail view kost normaal 0 credits omdat data al bestaat na signup

---

## 4. Optimalisatie Effect

### Zonder Optimalisatie
- Elke signup: 26 credits
- Elke detail view: 1 credit

### Met Optimalisatie
- Eerste signup per bedrijf: 26 credits
- Volgende signups: 0 credits ✅
- Company detail view (na signup): 0 credits ✅ (data bestaat al)
- Competitor detail view (eerste keer): 1 credit
- Competitor detail view (volgende keren): 0 credits ✅

**Besparing:** ~78% op totale kosten

---

## 5. Conclusie

✅ **Voldoende geoptimaliseerd:**
- Signup: 80% besparing (volgende gebruikers = 0 credits)
- Detail views: 54% besparing (volgende views = 0 credits)
- Totaal: 78% besparing

**Realistische kosten:**
- 100 nieuwe bedrijven/maand: ~3,200 credits
- 50 nieuwe bedrijven/maand: ~1,850 credits

---

**Document versie:** 1.0  
**Laatste update:** 2025-01-XX  
**Status:** ✅ Compleet
