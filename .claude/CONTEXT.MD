# Meal Prep — Project Context for Claude Code

## What this is

A self-hosted weekly meal planning system for a household of 2 in Wellington, New Zealand.
It scrapes real grocery prices from Pak'nSave Lower Hutt, uses Claude AI to generate 
weekly meal plans within a $60 budget, and serves them via a mobile-optimised PWA 
accessible over Tailscale.

Everything runs on a TrueNAS Scale homelab. No public internet exposure.

---

## Infrastructure

| Component | Where | Notes |
|---|---|---|
| TrueNAS Scale | 192.168.1.85 | Home NAS, all containers run here |
| MongoDB | TrueNAS container | Port 27017, two databases |
| Local Docker Registry | TrueNAS container | localhost:5000 |
| Tailscale | TrueNAS + iPhone | Private mesh network for remote access |
| Pak'nSave Scraper | TrueNAS cron job | Runs Mon/Wed/Fri via docker run |
| meal-api | TrueNAS container | FastAPI, port 8000 |
| meal-pwa | TrueNAS container | Nginx serving static PWA, port 3000 |

---

## Repository Structure

```
meal-prep/
├── meal-api/                  ← FastAPI backend
│   ├── src/
│   │   ├── main.py            ← FastAPI app, CORS, router registration
│   │   ├── database.py        ← MongoDB connection and clean() helpers
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── plans.py       ← /api/plan/* endpoints
│   │       ├── bundles.py     ← /api/bundle/* endpoints (to be built)
│   │       ├── recipes.py     ← /api/recipes/* endpoints
│   │       └── shopping.py    ← /api/shopping/* endpoints
│   ├── .env                   ← MONGO_URI (gitignored)
│   ├── .env.example
│   ├── Dockerfile
│   └── requirements.txt
│
└── meal-planner/              ← Python CLI meal planning pipeline
    ├── src/
    │   ├── main.py            ← Entry point, orchestrates pipeline
    │   ├── config.py          ← App constants (budget, serves, categories)
    │   ├── models.py          ← MarketData, Meal, MealPlan dataclasses
    │   ├── planner.py         ← Queries MongoDB paknsave-pricing for market data
    │   ├── claude.py          ← 4-call Claude API pipeline
    │   ├── mongodb.py         ← Read/write to paknsave-meals database
    │   └── excel.py           ← Excel generation (stub, part 3)
    ├── response.json          ← Last raw Claude API response (for testing)
    ├── .env                   ← MONGO_URI + ANTHROPIC_API_KEY (gitignored)
    ├── .env.example
    └── requirements.txt
```

---

## MongoDB Databases

### `paknsave-pricing` (written by scraper, read by planner)

**Collection: `products`**
```json
{
  "_id": "P12345678",
  "name": "Tegel Chicken Thighs",
  "size": "1kg",
  "category": "chicken",
  "sourceSite": "paknsave.co.nz",
  "storeId": "PAK'nSAVE Lower Hutt",
  "currentPrice": 9.99,
  "unitPrice": "9.99/kg",
  "isSpecial": true,
  "priceHistory": [
    { "date": "2026-05-01", "price": 12.99 },
    { "date": "2026-05-03", "price": 9.99 }
  ],
  "avgPrice90d": 12.24,
  "minPrice90d": 9.99,
  "maxPrice90d": 12.99,
  "firstSeen": "2026-03-01",
  "lastChecked": "2026-05-03"
}
```

**Collection: `scrape_runs`** — audit log of each scraper execution.

---

### `paknsave-meals` (written and read by planner + API)

**Collection: `bundles`** ← PRIMARY collection, replaces old `shopping_lists`

A bundle is a generated set of 5 recipes for a specific week.
Selecting a bundle sets what the PWA shows for that week.

```json
{
  "_id": "ObjectId",
  "bundleId": "winter-warmers-a1b2c3",
  "week": "2026-05-05",
  "active": true,
  "weekSummary": "Hearty winter meals built around chicken thighs on special",
  "estimatedTotal": 54.20,
  "recipeIds": [
    "chicken-curry-abc123",
    "pork-stew-def456",
    "lamb-soup-ghi789",
    "chicken-stir-fry-jkl012",
    "beef-mince-pasta-mno345"
  ],
  "priceSnapshotDate": "2026-05-03",
  "generatedBy": "claude",
  "createdAt": "datetime",
  "updatedAt": "datetime"
}
```

**Key design decisions:**
- `shoppingList` is NOT stored on the bundle — it is always derived on the fly
- Shopping list endpoint fetches the bundle's recipes, deduplicates ingredients, 
  looks up current prices from `paknsave-pricing`, returns the list
- This means prices are always current and custom bundles just work
- `estimatedTotal` is a cached value, refreshed when prices are re-fetched
- `generatedBy: "claude" | "user"` — groundwork for user-created custom bundles

---

**Collection: `recipes`**

Recipes accumulate over time and are reused across bundles.
Ingredients have amounts but NO prices — prices are always looked up live.

```json
{
  "_id": "ObjectId",
  "recipeId": "chicken-curry-abc123",
  "name": "Thai Chicken Curry",
  "serves": 2,
  "leftovers": true,
  "cookTime": "45 min",
  "description": "Aromatic coconut curry with chicken thighs",
  "recipeUrl": "https://www.recipetineats.com/thai-chicken-curry/",
  "source": "claude",
  "ingredients": [
    {
      "name": "Chicken Thighs",
      "amount": "600g",
      "fromSpecial": true,
      "sharedWith": ["pork-stew-def456"]
    }
  ],
  "method": [
    "Step 1: Season chicken...",
    "Step 2: Heat oil in pan..."
  ],
  "usageHistory": ["2026-05-05", "2026-04-28"],
  "bundleHistory": ["winter-warmers-a1b2c3"],
  "createdAt": "datetime",
  "updatedAt": "datetime"
}
```

---

## API Endpoints

### Bundles
```
GET  /api/bundle/latest              → active bundle for most recent week
GET  /api/bundle/week/{week}         → all bundles for a week
GET  /api/bundle/{bundleId}          → specific bundle with full recipe data
POST /api/bundle/{bundleId}/activate → set as active for its week
GET  /api/bundle/{bundleId}/shopping → derive shopping list from recipes + live prices
POST /api/bundle/{bundleId}/refresh-prices → recalculate estimatedTotal from current DB prices
```

### Recipes
```
GET /api/recipes                     → all recipes
GET /api/recipes/{recipeId}          → single recipe
GET /api/recipes?week={week}         → recipes used in a specific week
GET /api/recipes?bundle={bundleId}   → recipes in a specific bundle
```

### Plans (legacy, maps to bundles)
```
GET /api/plan/latest                 → redirects to active bundle
```

---

## The Claude Pipeline (meal-planner)

4 sequential API calls, each with one focused job:

```
Call 1 — Analyse market data
  Input:  raw price data from paknsave-pricing MongoDB
  Output: structured summary of best proteins, vegetables, specials this week
  Tokens: ~1,500 output

Call 2 — Plan 5 meals  
  Input:  market summary from Call 1
  Output: 5 meal names, proteins, estimated costs — no recipes yet
  Tokens: ~2,000 output

Call 3 — Generate recipes
  Input:  approved meal plan from Call 2 + market summary
  Output: full recipe for each meal — ingredients (with amounts, no prices) + method steps
  Tokens: ~4,000 output

Call 4 — Generate shopping list
  Input:  all 5 recipes from Call 3
  Output: deduplicated shopping list with shared ingredients combined
  Tokens: ~2,000 output
```

**Running the planner:**
```bash
cd meal-planner
python src/main.py        # load from response.json (for testing)
python src/main.py api    # call Claude API and store results
```

---

## PWA (meal-pwa — separate repo, served by Nginx on port 3000)

Three views optimised for phone use:

| View | Purpose |
|---|---|
| This Week | Active bundle overview — 5 meals, budget, tap to open recipe |
| Shopping | Tick-off checklist derived from active bundle, persists via localStorage |
| Recipes | List of this week's recipes, tap for detail + step-by-step cook mode |

**Version switching:** Header button opens a bottom sheet showing all bundles generated
for the current week. Tap any to activate it — PWA reloads with that bundle's recipes
and shopping list.

---

## User Preferences & Constraints

```python
BUDGET       = 60.00   # NZD per week
SERVES       = 2       # people
LEFTOVERS    = True    # batch cooking encouraged

PROTEIN_CATS = ["chicken", "pork", "beef-lamb", "mince-sausages"]
BEEF_MINCE_SPECIAL_ONLY = True  # only include if on special this week

EXCLUDE_CATS = ["seafood", "canned-fish", "frozen-seafood"]
EXCLUDE_KEYS = ["mushroom", "seafood", "fish", "prawn", 
                "shrimp", "salmon", "tuna", "offal", "organ"]
```

---

## What's Built vs What's Next

### ✅ Built and working
- Pak'nSave scraper (forked from Jason-nzd/pakn-scraper, MongoDB output added)
- MongoDB running on TrueNAS with `paknsave-pricing` and `paknsave-meals` databases
- 4-call Claude pipeline generating meal plans
- FastAPI serving plan/recipe/shopping endpoints
- PWA with This Week / Shopping / Recipes views + Cook Mode + Version switching
- Scraper runs Mon/Wed/Fri via TrueNAS cron job

### 🔨 In progress
- Migrating from `shopping_lists` collection to `bundles` collection
- Removing stored shopping lists — derive on the fly from recipes + live prices
- Adding `recipeId` slug-hash identifier to recipes (replacing `id: "M1"`)
- Shopping list endpoint that does live price lookup from `paknsave-pricing`

### 📋 Planned
- Custom bundle creation (user picks their own recipes)
- Recipe browser (all accumulated recipes, not just this week)
- "Re-fetch prices" button on old bundles
- Excel export of shopping list
- Push notification when new plan is generated

---

## Deployment

```bash
# Build and push from Mac
docker build --platform linux/amd64 -t 192.168.1.85:5000/meal-api:latest --load .
docker push 192.168.1.85:5000/meal-api:latest

# Pull and restart on TrueNAS (via SSH or cron)
docker pull localhost:5000/meal-api:latest
# Then restart app from TrueNAS UI
```

**TrueNAS app network:** `ix-mongodb1_default`
All containers on this network can reach MongoDB at its container hostname.

---

## Current Issues / Notes for Claude Code

1. **`mongodb.py` in meal-planner** — currently stores `shopping_list` inside the bundle 
   document. This needs to be removed. Shopping list should be derived by the API, not stored.

2. **Recipe IDs** — currently using `"id": "M1"` style IDs from Claude's JSON output.
   Need to migrate to `recipeId: "slug-hash"` format. The `generate_recipe_id()` function
   exists in `mongodb.py` but isn't wired up end-to-end yet.

3. **`bundles` collection** — currently named `shopping_lists`. Rename or migrate.

4. **`sharedWith` on ingredients** — Claude generates `sharedWith: ["M2", "M3"]` using 
   the old M1/M2 IDs. Once recipeIds are slugs, this needs to reference slug IDs instead.
   The UI uses this to show "shared with" on the shopping list.

5. **planner.py** — imports `MONGO_URI` from `config.py` but config.py no longer exports 
   secrets. Should import from `os.environ` directly with `load_dotenv()`.

6. **meal-pwa** — currently in a separate directory, not shown in the VS Code workspace.
   May need to be added to the meal-prep monorepo or kept separate.