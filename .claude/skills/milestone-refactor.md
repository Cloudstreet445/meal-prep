---
name: milestone-refactor
description: Run after a Linear milestone is marked complete — audit code structure, break up monolithic files, and ensure each layer lives in the right place.
---

# Milestone Refactor

After a Linear milestone is marked complete, run this audit before closing it out.
The goal is to prevent structural debt from accumulating across iterations.

---

## 1. Identify files that have grown too large

Flag any file that exceeds these thresholds:

| Repo | Threshold | Notes |
|------|-----------|-------|
| `pakn-scraper` (C#) | > 200 lines | Check `src/` |
| `paknsave-planner` (Python) | > 150 lines | Check `src/` or root `.py` files |
| `meal-api` (Python) | > 150 lines | Check `src/routers/`, `src/models/` |
| `meal-pwa` (JS/React) | > 200 lines | Check `src/components/`, `src/pages/` |

Run:
```bash
find /Users/blake/code/meal-prep -name "*.cs" -o -name "*.py" -o -name "*.ts" -o -name "*.tsx" \
  | grep -v node_modules | grep -v __pycache__ | grep -v ".venv" | grep -v "obj/" | grep -v "bin/" \
  | xargs wc -l | sort -rn | head -20
```

---

## 2. Apply the correct layer structure per repo

### `pakn-scraper` (C#)
```
src/
  Program.cs          ← entry point, CLI args, loop control only
  MongoDB.cs          ← all MongoDB I/O
  Scraper.cs          ← Playwright scraping logic only
  Utilities.cs        ← pure helper functions (unit price, slug, etc.)
  Models.cs           ← record types / DTOs
tests/
  MongoDBTests.cs     ← MongoDB integration tests
  UtilitiesTests.cs   ← pure function unit tests
  ScraperTests.cs     ← Playwright integration tests (marked [Ignore] for CI)
```

### `paknsave-planner` (Python)
```
src/
  ai/
    claude.py         ← Claude API pipeline (4-call chain)
  db/
    mongodb.py        ← all MongoDB I/O
  main.py             ← entry point / orchestration only
  planner.py          ← market data queries and plan logic
  models.py           ← dataclasses / TypedDicts
  config.py           ← constants and env config
scripts/
  seed.py             ← one-off data scripts (not part of the app module)
tests/
  test_planner.py
  test_mongodb.py
  test_models.py
  test_id_generators.py
```

### `meal-api` (Python / FastAPI)
```
src/
  main.py             ← app setup, router registration only
  routers/
    bundles.py        ← /api/bundles routes
    recipes.py        ← /api/recipes routes
    shopping.py       ← /api/shopping routes
  models/
    bundle.py         ← Pydantic models for bundles
    recipe.py         ← Pydantic models for recipes
    shopping.py       ← Pydantic models for shopping
  db.py               ← get_db, get_pricing_db dependency functions
tests/
  conftest.py
  test_bundles.py
  test_recipes.py
  test_shopping.py
  test_helpers.py
```

### `meal-pwa` (JS / React)
```
src/
  components/         ← reusable, stateless UI pieces
  pages/              ← route-level components (one per page)
  hooks/              ← custom React hooks
  utils/              ← pure helper functions
  api/                ← API client functions (fetch wrappers)
  types/              ← TypeScript type definitions
```

---

## 3. Refactoring rules

**Files**
- One responsibility per file. A router file should not contain business logic. A DB file should not contain formatting logic.
- If a file imports from more than 3 unrelated modules, it may be doing too much.
- No utility functions defined inline in route handlers — extract to `utils/` or a dedicated module.
- Correct naming - Somethings might have legacy names, update to reflect what this should be called - correct termanology

**Functions**
- Functions longer than 40 lines are a code smell — break into smaller named steps.
- A function that both fetches data AND transforms it should be split into two.
- No deeply nested conditionals (> 3 levels) — extract into named helper functions with early returns.

**Constants & config**
- Magic numbers and magic strings belong in a constants file or config, not inline.
- URLs, thresholds (e.g. 0.90 for isSpecial), and limits (e.g. 39-entry history) should be named constants.

---

## 4. What NOT to do

- Do not move things just for symmetry. Only refactor if there's a real structural problem.
- Do not change behaviour during a refactor — if logic moves, tests must still pass.
- Do not create new abstraction layers (base classes, generic repositories, etc.) unless the same pattern appears 3+ times.
- Do not split a file just because it's long — split when it has multiple distinct responsibilities.

---

## 5. Run tests after any structural change

After any file moves or splits, run the full suite to confirm nothing broke:

```bash
/Users/blake/code/meal-prep/run_tests.sh
```

Only proceed to close the milestone if all tests pass (or pre-existing failures are documented).

---

## 6. Real examples from this codebase

These are structural problems that have already been caught and fixed — use them as a guide for the kind of thing to look for.

**`pakn-scraper/src/Program.cs` was 816 lines — Playwright methods extracted to `Scraper.cs`**
Entry point files should only contain the entry point. All Playwright browser methods (`EstablishPlaywright`, `DOMElementToProduct`, `OpenInitialPageAndSetLocation`, `SetGeoLocation`, `GetStoreLocationName`, `RoutePlaywrightExclusions`) were moved to `Scraper.cs` using `partial class Program`. `Program.cs` now contains only `Main()` and the store loop.

**`meal-api/src/routers/bundles.py` had helper functions + route handlers — helpers extracted to `helpers.py`**
A router file was acting as a utility module. `shopping.py` was already importing `_derive_shopping_list` from `bundles.py`, which signalled these helpers didn't belong there. Moved `_normalise_name`, `_guess_category`, `_enrich_ingredient`, `_derive_shopping_list`, `_clean`, `_get_bundle_with_recipes` to `helpers.py`. Both `bundles.py` and `shopping.py` now import from `helpers.py`.

**`paknsave-planner/src/` had a flat pile of scripts — grouped by layer**
`claude.py` → `src/ai/claude.py`, `mongodb.py` → `src/db/mongodb.py`, `seed.py` → `scripts/seed.py`. Scripts (one-off runners) don't belong alongside application modules. AI calls and DB calls each have a natural home. Import paths updated throughout (`from db.mongodb import ...`, `from ai.claude import ...`). Tests updated to match new patch paths (`patch("db.mongodb._client", ...)`).

---

## 7. Close the milestone in Linear

After the structural audit (and any refactoring) is complete and tests pass:

1. Add a brief comment to the Linear milestone noting what was cleaned up (or "no structural issues found").
2. Mark the milestone as Done using `mcp__claude_ai_Linear__save_milestone`.
