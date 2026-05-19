# Kai Planner — Project Context

_Generated 2026-05-12. Use as orientation for an AI assistant._

---

## What This Is

A self-hosted weekly meal planning system for a household of 2 in Wellington, NZ. It scrapes PAK'nSAVE Lower Hutt prices, uses Claude AI to generate meal plans within a $60 NZD/week budget, and serves a mobile PWA over the home network and Tailscale.

**Not a product. A personal homelab project.** No public internet exposure. All services live on TrueNAS Scale at `192.168.1.85`.

---

## Repo Layout

```
meal-prep/
├── pakn-scraper/        # C# .NET 8 — scrapes paknsave.co.nz prices into MongoDB
├── paknsave-planner/    # Python — queries prices, calls Claude 4x, stores recipes/bundles
├── meal-api/            # Python FastAPI — serves meals/shopping/bundles to the PWA
├── meal-pwa/            # Vanilla JS PWA — 3-tab mobile UI, bundle switcher, cook mode
└── build-and-push.sh    # Docker build + push to local registry at 192.168.1.85:5000
```

---

## Data Flow

```
PAK'nSAVE website
      │  Playwright scrape (11s delay/page)
      ▼
pakn-scraper  ──upsert──▶  MongoDB: paknsave-pricing.products
                                     (price, unitPrice, isSpecial, 90d stats)
                                       │
                           query cheap/special items
                                       │
                                       ▼
                            paknsave-planner
                            ├─ Call 1: Analyse market data
                            ├─ Call 2: Plan 5 meals
                            ├─ Call 3: Generate full recipes
                            └─ Call 4: Generate shopping list
                                       │ upsert
                                       ▼
                            MongoDB: paknsave-meals
                            ├─ recipes  (ingredients + method)
                            └─ bundles  (recipeIds, week, active)
                                       │
                                  FastAPI JSON
                                       │
                                       ▼
                                    meal-api
                                       │
                                    meal-pwa
                            3 tabs: This Week · Shopping · Recipes
```

---

## SERVICE 1: pakn-scraper (C# .NET 8)

Headless Chromium (Playwright + Stealth), geolocation set to Lower Hutt (-41.2166, 174.9080). Extracts products by `data-testid`, upserts to MongoDB, appends price history only when price changed >$0.05. Detects specials: `currentPrice < 90d_avg * 0.90`.

Key files: `src/Program.cs`, `src/Records-Structs.cs`, `src/MongoDB.cs`, `src/Utilities.cs`, `src/Urls.txt`, `src/ProductOverrides.txt`

---

## SERVICE 2: paknsave-planner (Python)

4-call Claude pipeline (`claude-sonnet-4-6`):
1. Analyse market data — rank proteins by $/kg, identify best veg/pantry/dairy, flag specials
2. Plan 5 meals — estimated costs, ≥2 with leftovers, total < $60
3. Generate full recipes — ingredients with `estimatedCost`, `fromSpecial`, `sharedWith` (other recipe IDs)
4. Generate shopping list — deduplicated across meals, week summary, estimatedTotal

**Run commands (from `paknsave-planner/`):**
```bash
python src/main.py          # load from response.json + store
python src/main.py api      # call Claude API + store
python src/seed.py          # seed test-data/*.json into MongoDB
```

Config constants: `BUDGET=60.00`, `SERVES=2`, `CLAUDE_MODEL=claude-sonnet-4-6`, `MAX_PROTEIN_PRICE=15.00`

---

## SERVICE 3: meal-api (Python FastAPI)

**Key API endpoints:**
```
GET  /api/bundle/latest                  — active bundle + full recipes
GET  /api/bundle/history                 — all weeks → bundles (newest first)
GET  /api/bundle/{bundle_id}             — specific bundle + full recipes
GET  /api/bundle/{bundle_id}/shopping    — derived shopping list with live prices
POST /api/bundle/{bundle_id}/activate    — set as globally active
POST /api/bundle/custom                  — create custom bundle from recipe picks
POST /api/plan/generate                  — generate new plan (library-first, AI fallback)
GET  /api/recipes/                       — list recipes (filter: ?week=, ?bundle=)
GET  /api/recipes/{recipe_id}            — single recipe detail
GET  /api/shopping/latest                — shopping list for active bundle
GET  /health
```

Shopping list is **derived at request time** from live prices — not stored. `_derive_shopping_list()` deduplicates ingredients across all bundle recipes by normalised name and enriches with current prices.

**Route order matters:** `/history` and `/latest` must be defined before `/{bundle_id}` catch-all in FastAPI.

**Deploy from Mac:**
```bash
cd meal-api
docker build --platform linux/amd64 -t 192.168.1.85:5000/meal-api:latest --load .
docker push 192.168.1.85:5000/meal-api:latest
# Restart container from TrueNAS UI
```

---

## SERVICE 4: meal-pwa (Vanilla JS)

Three-tab mobile PWA. Dark theme only. Fonts: DM Mono (UI), Fraunces (week summary italic).

**Tabs:**
1. **This Week** — week summary, stat bar (dinners / spend / budget), meal cards. Swipe right on a card to mark as cooked (persists to localStorage by bundleId).
2. **Shopping** — checklist with progress bar, special 🔥 deal badges (strong/good/fair tiers), quantities aggregated across meals. Ticked items persist to localStorage per week.
3. **Recipes** — library-first list. Week meals shown first, then full library. Filter chips for protein type and cook time. Ratings visible in list view. Tap → detail with ingredients + method steps + "Start Cooking".

**Bundle switcher** (bottom sheet): "↕" icon in header. Shows this week's bundles + previous weeks (collapsible). Active state is `b.bundleId === plan?.bundleId` (NOT the DB `active` flag).

**Cook mode:** Full-screen step-by-step overlay with progress dots, rating prompt on finish.

**Design tokens (CSS variables):**
```css
--bg: #0f1410;   --bg2: #1a2018;   --bg3: #232e20;
--green: #4caf6e;
--text: #e8f0e5;  --text-dim: #7a9e7e;  --text-muted: #6b7f9e;
```

**API path:** `app.js` uses `/api` (relative path). `nginx.conf` proxies `/api/` → internal API host. The internal IP is never in client JS.

**Local dev:**
```bash
cd meal-pwa/static && python3 -m http.server 3000
```

---

## MongoDB Schemas

### paknsave-pricing.products
```json
{
  "_id": "P12345",
  "name": "Chicken Breast 500g",
  "category": "chicken",
  "currentPrice": 8.50,
  "unitPrice": "17.00/kg",
  "isSpecial": false,
  "avgPrice90d": 8.42,
  "minPrice90d": 7.99,
  "maxPrice90d": 9.50,
  "priceHistory": [{ "date": "2026-05-04", "price": 8.50 }],
  "lastChecked": "2026-05-04"
}
```

### paknsave-meals.recipes
```json
{
  "recipeId": "chicken-stir-fry-a1b2c3",
  "name": "Quick Chicken Stir-Fry",
  "serves": 2,
  "leftovers": true,
  "cookTime": "30 min",
  "ingredients": [{
    "name": "Chicken Breast",
    "amount": "400g",
    "estimatedCost": 6.80,
    "fromSpecial": false,
    "sharedWith": ["other-recipe-slug-xyz"]
  }],
  "method": ["Step 1...", "Step 2..."],
  "ratings": [{ "score": 4, "date": "2026-05-04" }],
  "lastUsedWeek": "2026-05-04",
  "usageHistory": ["2026-05-04"],
  "bundleHistory": ["spring-special-a1b2c3"]
}
```

### paknsave-meals.bundles
```json
{
  "bundleId": "spring-special-a1b2c3",
  "week": "2026-05-04",
  "active": true,
  "weekSummary": "Spring greens and chicken specials",
  "estimatedTotal": 58.95,
  "recipeIds": ["chicken-stir-fry-...", "..."],
  "priceSnapshotDate": "2026-05-04"
}
```

**Active flag rule:** Only ONE bundle across ALL weeks has `active: true`. Both `store_bundle` and `activate_bundle` run `update_many({}, {$set: {active: false}})` before activating.

`estimatedTotal` on the bundle is recomputed live (same deduplication logic as the shopping list) so it always matches what the shopping tab shows.

---

## Infra

| Service | Image | Port | Host |
|---------|-------|------|------|
| meal-api | 192.168.1.85:5000/meal-api:latest | 8000 | TrueNAS |
| meal-pwa | 192.168.1.85:5000/meal-pwa:latest | 3000 | TrueNAS |
| pakn-scraper | 192.168.1.85:5000/pakn-scraper:latest | — | TrueNAS (on-demand) |
| MongoDB | (managed by TrueNAS app) | 27017 | TrueNAS |

All containers share `ix-mongodb1_default` external Docker network.

---

## What Was Recently Built (last ~2 weeks)

In rough chronological order (newest last):

- **Multi-store scraper + store selector** — scraper handles multiple PAK'nSAVE locations; PWA settings let you switch store
- **Settings screen** — budget input, exclusion list editor, preferences (pantry toggle etc.)
- **Custom bundle builder** — "Build my own plan" with 5 empty meal slots + recipe picker from library
- **Recipe library features** — filter chips (protein type, cook time), ratings after cook mode, future-safe rating schema (array not single value)
- **Push notifications** — service worker background check for new prices; notification on plan generation complete
- **Cooking term glossary** — inline highlights in cook mode
- **Ingredient substitution suggestions** — static map + live pricing, no AI, shown in shopping list
- **Bundle switching UX** — bottom sheet redesign, clearer active state, collapsible weeks
- **Mobile layout audit** — responsive fixes across all tabs
- **Shopping list quantity aggregation** (MEA-63) — compatible units summed across meals (1 kg + 500 g → 1.5 kg)
- **Cooked meal tracking** (MEA-49) — swipe right to mark meal as done, persists by bundleId
- **Recipes tab restructure** (MEA-48) — week meals shown first, then full library
- **Deal tiers** (MEA-46) — colour-coded badges (strong/good/fair) with `priceSavings` from backend
- **WCAG AA contrast fix** (MEA-45) — `--text-muted` corrected from #475569 → #6b7f9e
- **Ratings in list view** (MEA-59) — rating badges visible without opening a recipe
- **UI declutter pass** (MEA-67) — icon-only plans button, compact stat bar, settings grouped into Planning/Preferences
- **estimatedTotal sync fix** — bundle's stored total now recomputed live from recipe data, always matches shopping tab
- **Library-first plan generation** (latest) — `POST /plan/generate` now picks from existing recipe library first (protein variety, LRU preference, budget-aware), falls back to AI planner only if <5 eligible recipes exist. Excludes current active bundle's recipes to avoid immediate repeats. 18 new unit tests.

---

## Open Backlog (Linear)

| ID | Title |
|----|-------|
| MEA-60 | Improve Weekly Plans: expand past bundles and apply selected week |
| MEA-61 | Build deterministic query builder for budget-aware recipe retrieval |
| MEA-62 | Experiment with ingredient subtraction to fit plans within budget |
| MEA-54 | Constrain enhancement suggestions by budget range and pantry context |
| MEA-55 | Create dedicated pantry flow with smart item suggestions |
| MEA-47 | Upgrade pantry tracker with quantity, category, and expiry metadata |
| MEA-56 | Add weekly price deltas and monthly average trend |
| MEA-36 | Revise substitution map — review coverage and pricing match quality |
| MEA-37 | Retrieve user location to auto-set nearest store |
| MEA-57 | Run Phase 2 feature opportunity workshop |
| MEA-58 | Run UX/design quality pass using targeted agent skills |
| MEA-64 | UI audit — identify worst button/layout offenders and apply quick fixes |
| MEA-65 | Define spacing, colour, and typography tokens for consistent UI |
| MEA-66 | Establish button placement rules and rebuild interactive components consistently |

---

## Known Conventions & Gotchas

- **HTML + CSS always together** — any new element in `index.html` or `app.js` must have a matching rule in `style.css`. Don't assume inheritance will be good enough.
- **Shopping list is derived, never stored** — prices are always live. Don't add a stored shopping list field to bundles.
- **Recipe IDs are slugs** — format `"meal-name-md5hash"`, generated deterministically by `generate_recipe_id()` in `mongodb.py`.
- **`sharedWith` on ingredients** references other recipe slug IDs — used by the shopping list UI to show cross-meal sharing.
- **`active` flag semantics** — exactly one bundle is active globally at any time. Activating one deactivates all others via `update_many`.
- **FastAPI route order** — `/history` and `/latest` routes must appear before `/{bundle_id}` in the router file.
- **API host** — never put the internal IP in client JS. It belongs in `nginx.conf` as `__API_HOST__` substituted at Docker build time (`--build-arg API_HOST=...`).
- **Planner service** — `paknsave-planner` is run manually on-demand, not as a persistent container. It seeds the DB and exits.
