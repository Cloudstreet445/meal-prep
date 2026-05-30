# Kai Planner — Codebase Review & Uplift Plan

The headline finding: **the "generate a cheap, protein-focused weekly plan from my budget and preferences" core — the one thing you said matters most — is partly disconnected from the user's actual settings.** It's not a tuning problem, it's a wiring problem. Details below.

---

## 🔴 Critical: plan generation ignores the logged-in user's settings

This is the single most important thing in the review.

- Every user's budget/serves/exclusions are saved per-user under `{"userId": ...}` (`settings.py:42,57`).
- But plan generation reads a **different document** — the shared anonymous fallback:

```python
# plans.py:28
settings   = db["settings"].find_one({"key": "default"}) or {}
budget     = float(settings.get("budget", 60))
exclusions = settings.get("exclusions", [])
```

So when a logged-in user sets a $90 budget and excludes mushrooms, the generator never sees it. It uses the global `{"key":"default"}` doc (or the hardcoded $60). The **only** per-user signal that survives is `user_id`, used for thumbs-up/down ratings.

**Net effect:** the onboarding you're worried about collects budget, store, and exclusions, saves them correctly… and then the generator throws them away. Fixing this one line (`_settings_key(user)` instead of `{"key":"default"}`) is the highest-leverage change in the whole repo.

---

## 1. Onboarding & settings — what's collected vs. used

**Onboarding** (3 steps, all skippable): store → budget + household size → done. Saves `{budget, serves, storeId, exclusions}` via `PUT /settings/`.

| Setting | Collected? | Stored? | **Actually used in plan gen?** |
|---|---|---|---|
| `budget` | ✅ | ✅ per-user | ⚠️ Only via shared default doc (bug above) |
| `exclusions` | ⚠️ no UI in onboarding | ✅ per-user | ⚠️ Same bug; also naive substring match ("lamb" matches "clamber") |
| `storeId` | ✅ | ✅ per-user | ❌ Generator hardcodes `paknsave-lower-hutt`; store only applied later when bundle is viewed |
| `serves` (household size) | ✅ | ✅ | ❌ **Never used anywhere** — recipes aren't scaled to household size |
| Pantry / inventory | ✅ (Pantry tab) | ⚠️ localStorage only, not backend (there's a `user_pantry` collection that the UI doesn't use) | ❌ Never consulted in generation or shopping |
| Protein preferences | ❌ not collected | — | Protein only used for *variety*, never preference |

**Gaps that matter for your goal:**
- **No dietary profile.** There's no vegetarian/vegan/halal/gluten-free flag — only a free-text exclusion list. For a budget meal app, structured diet tags would prevent the substring fragility and let you say "cheapest plan that's still vegetarian."
- **Household size is dead weight.** You ask for it in onboarding then ignore it. Either scale recipe quantities/costs by `serves`, or stop asking.
- **Pantry is cosmetic.** It lives in localStorage, isn't synced across a household, and never reduces what you buy or what you cook. This is the biggest missed "save money" lever — using up what you already have.

---

## 2. How plans are generated (and where it falls short of "cheap protein")

The algorithm (`helpers.py:_select_from_library`) is a clean two-pass greedy:
1. Filter out excluded ingredients + thumbs-down recipes.
2. Score each recipe by **recency** (staler = higher) × **rating** (liked = ×1.3).
3. **Pass 1:** guarantee one recipe per protein type (chicken/pork/beef/lamb/other), stalest protein first.
4. **Pass 2:** fill remaining slots with highest-scored recipes that still fit budget.

It's a sound *variety* engine. But for *"cheap, protein-for-your-budget"* it's missing the economic core:

- **No cost optimization.** Budget is only a stop ("does it still fit?"), never an objective. It won't prefer a $9 chicken meal over a $16 lamb meal — selection is driven by recency, not value. Two plans can both be "under budget" while one wastes $30.
- **No protein-per-dollar.** You want protein that fits the budget, but there's no notion of grams-of-protein or cost-per-serve-of-protein. Protein is just a category label for rotation.
- **Costs are stale at generation time.** It selects on `baselineCost`/`costTier` (budget=$10/mid=$17/premium=$28 buckets), not live store prices. Live pricing is only applied later when the bundle is *viewed*. So the budget decision is made on rough estimates, and **specials/sales never influence which meals get picked** — a huge miss for a budget app where "what's cheap this week" should drive the plan.
- **Hard fail.** If 5 recipes don't fit, it returns nothing (422) instead of degrading to 4 meals or flagging "your budget is tight."

**The uplift that matches your mission:** make generation *price-aware and value-seeking* — score recipes on live cost-per-serve (and ideally cost-per-gram-of-protein), bias toward proteins on special this week, and optimize total value within budget rather than just staying under it.

---

## 3. Does the price database need better variables/links? — Yes

The scraper currently stores: `id, name, size, category, sourceSite` + per-store `{currentPrice, unitPrice, isSpecial, priceHistory, avgPrice90d, minPrice90d, maxPrice90d, firstSeen, lastChecked}`. The 90-day history is genuinely good. But for your goals it's missing the structured fields that make matching and "cheap protein" possible:

**Worth adding to the scraped product:**
- **`brand`** (structured, not buried in name) — needed for the "see other brands" feature below.
- **`packSizeG` / `packSizeMl` / `unit`** (parsed numerically at scrape time) — right now the API re-parses size out of the *name* with regex on every request. Parse once, store it.
- **`pricePerKg` / `pricePerUnit`** (normalized numeric) — `unitPrice` is a display string ("3.40/L"). A numeric normalized field is what lets you rank "cheapest chicken per kg."
- **`nutrition` (esp. protein grams per 100g)** — this is the missing link for *protein-aware budgeting*. Without it you can target "cheap" but not "cheap protein." Pak'nSave product pages expose nutrition panels; capturing protein/100g would let you compute **cost per gram of protein** — the exact metric your app is about.
- **`inStock` / availability** and a stable **`productUrl`** (deep link so users can verify/add to a real cart).
- A **canonical ingredient tag** (e.g. map "Pams Chicken Breast Skinless 1kg" → canonical `chicken_breast`) so recipe ingredients link to a *class* of products, not a fuzzy name search.

The current matching is **word-relevance scoring, not price ranking**. It picks the best *name match* and only breaks ties by price — so it does **not** reliably pick the cheapest chicken breast. Adding `brand`, numeric `pricePerKg`, and a canonical tag turns matching from "fuzzy text guess" into "look up the canonical ingredient, rank candidates by price-per-unit."

---

## 4. Chicken breast → cheapest by default, tappable for other brands? — Yes, and here's the model

Your instinct is exactly right, and the data model should support it:

**Default behavior:** shopping list shows the **cheapest in-stock product** for the canonical ingredient (e.g. cheapest chicken breast per kg at the user's store). Right now it shows the best *name match*, which isn't the same thing — fix matching to rank by normalized price.

**Tap to swap:** show the other candidates for that ingredient — different brands, organic/free-range, bigger packs — with each one's price and price-per-kg, and let the user pick. Persist the choice on the shopping item (a `chosenProductId` override) so their total updates and the choice sticks.

This needs two things you don't have yet:
1. **Brand + numeric unit price as structured fields** (section 3) so the alternatives list is meaningful and sortable.
2. **A backend swap endpoint + per-item product override** — today `suggestSubstitute()` only *shows* suggestions; it can't actually change the selected product or the running total. There's no endpoint to lock an item to a chosen product.

**Should the price checker save more metadata? Yes** — same list as section 3. The two highest-value additions are **brand** (enables the brand-picker UX you described) and **protein-per-100g** (enables the cost-per-protein ranking your whole app is premised on).

---

## Also worth knowing

- **MEA-129 (unit conversion)** is narrower than the note implies. The proportional cost math is actually fine; the real bug is that two recipes using the same ingredient in *incompatible culinary units* (e.g. "1 cup" + "500g" garlic) can't be summed, so they split into confusing per-recipe line items. Fix = convert culinary units → grams/ml *before* merging, using the existing `_CULINARY_TO_GRAMS` table.
- **Pantry isn't backend-synced** despite a `user_pantry` collection existing — household members don't share a pantry, and it's lost if localStorage clears.

---

## Recommended priority order

1. **Fix the settings wiring** (`plans.py:28`) so generation uses the logged-in user's budget/exclusions/store. *One-line-ish fix, unlocks everything else.* 🔴
2. **Make generation price-aware** — score on live cost-per-serve, bias toward specials, optimize value within budget instead of just fitting.
3. **Enrich the scraper**: `brand`, numeric `packSize`/`pricePerKg`, `productUrl`, and **protein-per-100g**.
4. **Cheapest-by-default + brand swap** in the shopping list (needs #3 + a swap endpoint with per-item override).
5. **Use `serves`** to scale quantities/costs, or drop it from onboarding.
6. **Backend pantry** that actually subtracts from the shopping list (and is household-shared).
7. Structured **diet tags** instead of free-text exclusions; **graceful budget degrade** instead of hard 422.

---

## Detailed Findings Reference

### Onboarding Flow (Complete)

**File:** `/home/user/meal-prep/meal-pwa/static/index.html` (lines 549-597) and `/home/user/meal-prep/meal-pwa/static/app.js` (lines 622-709)

**Step 0: PAK'nSave Store Selection**
- Data collected: `storeId` (e.g., `paknsave-lower-hutt`)
- Skippable: YES
- Default: `paknsave-lower-hutt`

**Step 1: Budget & Household Size**
- Data collected: `budget` (20–500 NZD, default 60), `serves` (1–10 people, default 2)
- Skippable: YES

**Step 2: Completion** (no data collection, confirmation screen)

Finalization via `PUT /settings/` sends `{ budget, serves, storeId, exclusions: [] }` — note `exclusions` starts empty with no onboarding UI to populate it.

### Settings Schema

**Backend MongoDB document** (`settings` collection):
```python
{
  "userId": str(uuid),              # Per-user, or "key": "default" for shared fallback
  "budget": float,                  # Default 60.0
  "serves": int,                    # Default 2 (UNUSED IN GENERATION)
  "exclusions": list[str],          # Default []
  "storeId": str,                   # Default "paknsave-lower-hutt"
}
```

**API endpoints:**
- `GET /settings/` — fetch settings (with defaults fallback)
- `PUT /settings/` — save settings (requires auth)
- `GET /settings/stores` — list available Pak'nSave store IDs

### Meal Plan Generation Algorithm

**Entry point:** `POST /api/plan/generate` → `meal-api/src/routers/plans.py:23-80`

**Core algorithm:** `meal-api/src/routers/helpers.py:_select_from_library()` (lines 148-260)

```python
1. Load all recipes except those already used this week
2. Filter: remove recipes with excluded ingredients (substring match)
3. Filter: remove thumbs-down recipes for this user
4. Score each recipe: recency (0.0 to 1.0 over 8 weeks) × rating multiplier (1.3× if liked)
5. Pass 1 (Protein Variety): 
   - For each protein type in least-recently-used order
   - Pick highest-scored recipe of that protein if it fits budget
6. Pass 2 (Fill Remaining):
   - Add highest-scored recipes that fit budget until 5 selected or candidates exhausted
7. Return 5 recipes or None (which causes 422 error)
```

**Cost calculation** (`_recipe_cost()`, lines 132-145):
- Priority: `baselineCost` > `costTier` estimate > sum of ingredient `estimatedCost`
- Tier estimates: budget=$10, mid=$17, premium=$28
- Costs used at generation time are **not live** — only updated when bundle is viewed later

**Budget handling:**
- Hard constraint: `if total + recipe_cost <= budget`
- No optimization for value
- No fallback if fewer than 5 recipes fit

**User settings actually used:**
- ✅ `user_id` (for ratings filtering)
- ❌ `budget` (reads from shared "default" doc instead of per-user)
- ❌ `exclusions` (reads from shared "default" doc instead of per-user)
- ❌ `storeId` (hardcoded to paknsave-lower-hutt)
- ❌ `serves` (never accessed)

### Price Database & Scraper

**Scraper location:** `/home/user/meal-prep/pakn-scraper/` (C# .NET 8.0)

**Product fields saved to MongoDB:**
```json
{
  "_id": "P1234567",
  "name": "Supreme Lite Milk",
  "size": "1L",
  "category": "milk",
  "sourceSite": "paknsave.co.nz",
  "searchTokens": ["supreme", "lite", "milk", ...],
  "storePrice": {
    "paknsave-lower-hutt": {
      "currentPrice": 3.40,
      "unitPrice": "3.40/L",           // String, not numeric
      "isSpecial": false,
      "priceHistory": [
        { "date": "2026-05-30", "price": 3.40 }
      ],
      "firstSeen": "2023-07-02",
      "lastChecked": "2026-05-30",
      "lastPriceChange": "2025-12-29",
      "avgPrice90d": 3.20,
      "minPrice90d": 2.95,
      "maxPrice90d": 3.40
    }
  }
}
```

**Missing fields (that would help):**
- `brand` (structured) — currently buried in `name`
- `packSizeG`, `packSizeMl` (numeric) — currently regex-parsed from name
- `pricePerKg` (numeric) — currently stored as string `unitPrice`
- `nutrition.proteinGrams100g` — not captured, blocks protein-per-dollar optimization
- `inStock` / `availability` — not tracked
- `productUrl` — no deep link to Pak'nSave product page
- `canonicalIngredient` — no mapping from product to ingredient class

### Ingredient → Product Matching

**Function:** `_enrich_ingredient()` (`meal-api/src/routers/helpers.py`, lines 385-482)

**Algorithm:**
1. Extract search words from ingredient name (min 3 chars)
2. Query pricing DB for products matching first word (regex, case-insensitive, limit 30)
3. Score each candidate: word-match bonus for each ingredient word found
4. Pick best candidate: highest word score wins; ties broken by lowest total pack cost
5. Calculate two prices:
   - `packPrice`: whole packs needed × unit price (what shopper pays at checkout)
   - `currentPrice`: (needed_g / pack_g) × unit_price (proportional budget share)

**Key limitations:**
- Picks **best name match**, not cheapest product
- No multi-product price comparison across brands/sizes
- Doesn't prefer products on special (except in deal-badge display after selection)

### Shopping List Structure

**Item returned by `GET /api/shopping/latest`:**
```json
{
  "name": "Chicken Breast",
  "amount": "400g",
  "amount_parts": [],           // Non-empty if culinary units prevent merging
  "category": "protein",
  "packPrice": 8.99,            // Whole-pack cost
  "currentPrice": 2.50,         // Proportional cost
  "estimatedCost": 2.50,        // Used for total calculation
  "matchedProduct": "Chicken Breast 400g",
  "isSpecial": false,
  "dealStrength": 15,           // % discount if on special
  "priceSavings": 1.25,
  "usedIn": ["r1", "r2"],       // Recipe IDs
  "usedInNames": ["Chicken Stir Fry", "Teriyaki Chicken"],
  "sharedWith": ["Chicken Stir Fry", "Teriyaki Chicken"]
}
```

**Running total:** Sum of `packPrice or estimatedCost` per unchecked item.

**Pantry handling:** Items flagged with "in pantry" badge if substring match to localStorage pantry; optional collapsible section to hide from list.

### MEA-129: Unit Conversion Issue

**Problem:** Two recipes using the same ingredient in incompatible culinary units (e.g., "1 cup garlic" + "500g garlic") can't be merged into a single shopping line.

**Root cause:** `_add_amounts()` helper fails to sum incompatible unit types, forcing the line to split into `amount_parts` with separate line items per recipe.

**Impact:** Confusing shopping list with redundant ingredient lines (e.g., two separate "Garlic" items showing "1 cup" and "500g").

**Fix:** Convert culinary units to canonical grams/ml *before* attempting to sum, using the existing `_CULINARY_TO_GRAMS` lookup table:
```python
_CULINARY_TO_GRAMS = {
  "clove": 5.0,
  "pinch": 0.5,
  "handful": 30.0,
  "cup": 240.0,  # (for volume)
  "tbsp": 15.0,
  ...
}
```

### Pantry Integration (Current State)

**Storage:**
- Frontend: `localStorage["pantry"]` — array of `{name, canonical}`
- Backend: `user_pantry` collection exists but is never queried in plan generation or shopping derivation

**Usage:**
- Shopping list shows "in pantry" badge for matched items (substring match)
- Optional `hidePantryFromShopping` toggle (client-side only)
- **Does NOT:** subtract quantities, calculate savings, or influence which meals are chosen

**What's missing:** backend-synced pantry that is household-shared, queryable during generation, and actually reduces shopping quantities.
