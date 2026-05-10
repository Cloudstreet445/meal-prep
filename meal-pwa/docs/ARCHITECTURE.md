# Meal PWA Architecture

## Purpose
This document defines the current technical architecture of the Meal PWA so code changes stay aligned with existing system behavior.

## System Overview
- Frontend is a static PWA served from `static/` (`index.html`, `app.js`, `style.css`, `sw.js`).
- Frontend communicates with backend via `/api/*` endpoints.
- Nginx proxies `/api` to the API service (see `nginx.conf` and inline notes in `static/app.js`).
- App is intentionally client-heavy: view state, UI transitions, and most interaction logic live in `static/app.js`.

## Runtime Components
- **UI shell**: Header, tab navigation, three primary views (This Week, Shopping, Recipes).
- **Overlay system**: Bottom sheets and full-screen overlays for settings, bundles, builder, picker, cook mode, ratings, substitutions.
- **Persistence layer (client)**:
  - `localStorage`: theme, pantry, checked shopping items (keyed by bundle), notification-dismiss state, last seen bundle.
  - In-memory state vars: active plan, recipe list, filters, settings snapshot, history data.
- **Service worker**: registration + periodic sync capability when supported.

## Files and Responsibilities
- `static/index.html`
  - Declares app shell structure and all overlay containers.
  - Should remain declarative (minimal logic in inline handlers only when required).
- `static/app.js`
  - Owns orchestration: fetch, state mutation, render, and UI event wiring.
  - Organized by feature sections (Week, Shopping, Recipes, Bundles, Settings, etc.).
- `static/style.css`
  - Owns visual language: tokens, component styles, state variants, and motion.
- `static/sw.js`
  - Handles service worker lifecycle and background sync behavior.
- `tests/*.test.js`
  - Covers utility/business logic and regression-prone transformations.

## Data Boundaries
- Server-owned data:
  - Active bundle and bundle history
  - Shopping list and estimated totals
  - Recipe library and rating persistence
  - App settings and available stores
- Client-owned data:
  - Theme preference
  - Pantry list
  - UI-only state (open overlays, selected tabs, local filtering)
  - Temporary progress state (checked shopping list entries)

## Canonical Client State Shape
- `plan`: active bundle payload (`bundleId`, `week`, `recipes`, `estimatedTotal`, summary text)
- `settings`: budget/serves/exclusions/store selection snapshot
- `allRecipes`: full recipe library list
- `historyData`: weekly bundle history data for switcher sheet
- `checked`: shopping item completion map keyed by item index for current bundle key
- `pantry`: user pantry entries (`name`, `canonical`) from localStorage

## Local Storage Contract
- `theme`: `"dark"` | `"light"`
- `pantry`: JSON array of pantry entries
- `checked_{bundleIdOrWeek}`: JSON object of shopping completion flags
- `notifPromptDismissed`: `"1"` when banner is dismissed
- `lastSeenBundleId`: used to detect newly generated bundles for notifications

Rules:
- Never change key formats without a migration strategy.
- Prefer additive migrations over destructive resets.
- Keep values JSON-serializable and versionable.

## API Surface (Current Usage)
- `GET /api/bundle/latest`
- `GET /api/bundle/history`
- `GET /api/bundle/week/{week}`
- `POST /api/bundle/{bundleId}/activate`
- `POST /api/bundle/custom`
- `GET /api/shopping/latest?store_id={id}`
- `GET /api/recipes/`
- `POST /api/recipes/{recipeId}/rate`
- `POST /api/substitutions/suggest`
- `POST /api/plan/generate`
- `GET /api/settings/`
- `PUT /api/settings/`
- `GET /api/settings/stores`

## Integration Reliability Rules
- All fetches must go through `apiFetch` / `apiPost` wrappers unless there is a strong reason not to.
- Every network call must have:
  - a visible loading state
  - a clear error fallback
  - logging context with section name
- UI should remain usable when one endpoint fails (degrade by view, not globally).

## UI Architecture Conventions
- Single-page app pattern with tab-driven view switching.
- Overlay-first interactions for secondary tasks (sheet/overlay instead of route changes).
- Design tokens are CSS variables defined in `style.css` (`:root` + theme variants).
- Dark mode defaults; light mode supported via media query and explicit theme toggle.

## State Management Rules
- Keep state colocated with feature blocks in `app.js` until module split is introduced.
- Use server as source of truth for plan, settings, and recipes.
- Use localStorage only for:
  - low-risk personalization
  - temporary UX continuity
  - data that can be safely recomputed from server
- Any key tied to a plan must be bundle-aware to avoid cross-week leakage.

## Render and Re-render Strategy
- Prefer targeted render functions per feature:
  - `loadWeek` + week section render
  - `loadShopping` + `renderShoppingItems`
  - `loadRecipes` + `renderRecipeList`
- Avoid full-app rerenders; preserve user context (tab, scroll, active overlay) where possible.
- For cross-view operations (example: bundle switch), use explicit reset + reload sequence.

## Error Handling Standard
- API failures must:
  - log via `log(section, message, data)`
  - show a user-readable fallback state in the affected view
  - avoid hard crashes that block unrelated views

## Accessibility and Semantics Architecture
- Interactive surfaces must be keyboard reachable or have equivalent accessible affordances.
- Icon-only controls require labels (`aria-label` where needed).
- Focus-visible behavior must remain consistent with token system.
- Accessibility regressions are architecture regressions, not cosmetic issues.

## Performance and UX Guardrails
- Keep interactions non-blocking and mobile-first.
- Prefer incremental rendering updates over full DOM rebuild when feasible.
- Respect `prefers-reduced-motion`.
- Keep touch targets and spacing optimized for handheld screens.

## Testing Expectations
- Preserve existing vitest coverage under `tests/`.
- Add/adjust tests for business logic changes in:
  - shopping list behavior
  - utility/transformation logic
  - filter and selection behavior where practical

## Change Impact Matrix
- **Week generation/switching changes**:
  - Validate Week, Shopping, and Recipes coherence after switch.
- **Shopping logic changes**:
  - Validate progress, checked persistence, pantry dimming, substitution entry points.
- **Recipe flow changes**:
  - Validate list filters, detail open/back, cook mode, rating writeback.
- **Settings changes**:
  - Validate save + reload behavior and store-aware fetch behavior.

## Architectural Debt Log
- `static/app.js` is monolithic and should be split by feature modules.
- State is mutable global scope; gradual extraction to isolated modules is recommended.
- API contracts are implicit; introduce typed contracts (JSDoc typedefs or TS) to reduce regressions.

## Planned Evolution (Near-Term)
- Split `static/app.js` into feature modules without changing UX contract.
- Introduce typed data contracts (JSDoc typedefs or TypeScript migration path).
- Formalize API client wrapper for retries, timeout handling, and consistent errors.
