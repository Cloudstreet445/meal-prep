# Meal PWA Product Flows

## Purpose
Define expected user flows so future implementation changes preserve behavior and UX quality.

## Flow Notation
- **Entry**: where user starts the flow
- **Core path**: expected happy path
- **Edge handling**: expected fallback behavior
- **Exit**: resulting state and next likely action

## Primary Flows

### 1) Open App and View Current Week
Entry: App launch

1. App initializes theme, pantry, settings.
2. App loads latest bundle (`/bundle/latest`).
3. Week summary and meal cards render.
4. User can open meal details from any meal card.

Edge handling:
- If settings fail, app continues with defaults.
- If week fetch fails, This Week shows recoverable error state.
- If recipes load later than week, core week UX still usable.

Success criteria:
- Week badge and budget pill show current values.
- Loading and failure states are clear and recoverable.

### 2) Generate New Plan
Entry: This Week view CTA

1. User taps `Generate new plan`.
2. Button enters loading state.
3. App calls `/plan/generate`.
4. On success, app refreshes week + shopping views.
5. Optional notification shown if permission is granted.

Edge handling:
- Generation errors surface in status text with retry path.
- CTA re-enables in all code paths (success/failure).

Success criteria:
- No duplicate triggers while generating.
- User gets explicit success/failure feedback.

### 3) Shop Weekly List
Entry: Shopping tab

1. User opens `Shopping` tab.
2. App loads `/shopping/latest?store_id=...`.
3. User checks/unchecks items.
4. Progress bar updates in real time.
5. Checked state persists for current bundle.

Edge handling:
- If list fetch fails, tab-local error shown without breaking other tabs.
- If no items, show explicit empty state.

Success criteria:
- Checked state does not leak between weeks/bundles.
- Pantry items are visibly distinct.

### 4) Browse and Open Recipes
Entry: Recipes tab

1. User opens `Recipes`.
2. App loads recipe library.
3. User filters by protein/time and/or searches.
4. User opens recipe detail.
5. User can start cook mode from detail.

Edge handling:
- If no results match search/filter, show meaningful empty state.
- If detail is opened for missing recipe id, fail safely (no crash).

Success criteria:
- Filters combine predictably.
- Back navigation returns to recipe list state.

### 5) Cook Mode and Rating
Entry: Recipe detail -> Start Cooking

1. User starts cook mode.
2. Steps advance via buttons or swipe.
3. On completion, rating overlay appears.
4. User submits thumbs up/down or skips.

Edge handling:
- Empty method should avoid entering broken step UI.
- Close action exits cleanly and releases wakelock.

Success criteria:
- Step position is clear at all times.
- Rating updates appear in recipe list/detail state.

### 6) Switch Weekly Bundle
Entry: Header `Weekly Plans` action

1. User opens weekly plans sheet.
2. User inspects this week and previous weeks.
3. User selects target bundle.
4. App activates bundle and reloads dependent views.

Edge handling:
- Failed activation shows sheet error and keeps prior active state.
- Re-selecting current bundle should no-op and close.

Success criteria:
- Active/viewing states are explicit.
- Switching updates week, shopping, and recipes coherently.

### 7) Build Custom Plan
Entry: Weekly Plans sheet -> Build my own plan

1. User opens `Build my own plan`.
2. User fills recipe slots via picker.
3. User saves custom bundle.
4. App reloads and shows selected plan.

Edge handling:
- Save blocked until at least one recipe is chosen.
- Failed save preserves user-selected slots for retry.

Success criteria:
- Save is blocked until at least one recipe is selected.
- Cost indicator updates as slots change.

### 8) Update Settings
Entry: Header settings action

1. User opens settings sheet.
2. User edits budget, serves, exclusions, pantry, store.
3. User saves settings.
4. App reflects updated values in active UI.

Edge handling:
- Invalid numeric values are validated inline/alerted.
- Failed save keeps sheet open and explains recovery path.

Success criteria:
- Validation prevents invalid budget/serves values.
- Store selection immediately influences shopping fetches.

## Cross-Cutting States
- **Loading**: every async flow shows progress.
- **Error**: every async flow exposes a recoverable message.
- **Empty**: list-type flows show meaningful empty state copy.
- **Offline/degraded**: failures should be isolated to affected view where possible.

## Flow Coupling Risks
- Week/bundle switching is tightly coupled to shopping and recipe context.
- Settings store change influences subsequent shopping fetches.
- Rating updates should reflect immediately in recipes UI to avoid stale confidence signals.

## Regression Checklist by Flow
- Open app: week loads, badge updates, no blank state lock.
- Generate: CTA disables/enables correctly and week refreshes.
- Shopping: progress and checked state persist for active bundle only.
- Recipes: filter/search combos remain deterministic.
- Cook mode: prev/next/done states and overlay transitions are stable.
- Bundle switch: all three core views reflect selected bundle.
- Builder: save path creates visible result in week context.
- Settings: persisted values round-trip and affect dependent fetches.

## Flow Ownership Map
- Week + generation: `loadWeek`, `generatePlan`
- Shopping: `loadShopping`, `renderShoppingItems`, `toggleItem`
- Recipes + detail: `loadRecipes`, `renderRecipeList`, `openRecipe`
- Cook mode: `startCooking`, `renderCookStep`
- Bundles: `loadBundleSheet`, `toggleWeek`, `selectBundle`
- Settings: `loadSettings`, `openSettings`, `saveSettings`
- Custom builder: `openBuilder`, `renderBuilderSlots`, `saveCustomBundle`

## Change Policy
When changing any flow:
1. Update this file if behavior changes.
2. Keep acceptance outcomes for the flow intact or explicitly redefine them.
3. Validate adjacent flows to avoid regressions (especially week/switch/shopping coupling).
