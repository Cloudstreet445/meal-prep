# Design Brief: Kai Planner PWA

_Self-authored from codebase analysis — no interview required._

---

## Problem

A household planning 5 dinners a week has no good tool that connects the supermarket specials to their plate. Spreadsheets are too slow, recipe apps don't know what's cheap this week, and generic meal planners ignore real-world budget constraints. The user needs a fast, opinionated weekly planner that surfaces what to cook, what to buy, and how to cook it — in the right order, at the right moment.

## Solution

A mobile-first PWA that ingests weekly Pak'nSave pricing data, uses AI to plan budget-optimal dinners, and presents the result as a scannable weekly view, a checkable shopping list, and a step-by-step cook mode. The interface is designed to be used standing in a supermarket aisle or standing at a kitchen bench — not sitting at a desk.

## Experience Principles

1. **Glanceable over comprehensive** — Every view should communicate its key information in under 3 seconds. Budget remaining, what's for dinner, what's left to buy. Numbers and status first, detail on tap.

2. **Quiet confidence over decoration** — The aesthetic should feel considered and calm. No gradients for their own sake, no animations that don't communicate state. The design earns trust by being precise.

3. **Context-aware hierarchy** — The active week is primary; history and settings are secondary. Overlays are for focused tasks only; they don't need to mimic the main views.

---

## Aesthetic Direction

- **Philosophy**: Editorial / Magazine — Fraunces (display serif) paired with DM Mono (monospace). This is deliberate and unusual. Fraunces gives the app warmth and personality; DM Mono grounds it in precision and data. The pairing signals "crafted, not generated."
- **Tone**: Calm, precise, slightly premium. Like a well-designed cookbook app built for someone who cooks seriously but practically.
- **Palette**: Dark forest-green. `#0f1410` is warmer and more organic than pure black — it reads as intentional. The `#4caf6e` green accent is the single functional colour: money, success, action.
- **Reference points**: Readymag editorial layouts, Notion dark mode precision, Linear's typographic density.
- **Anti-references**: Generic iOS recipe apps (white cards, red accents), food delivery apps (photography-heavy, marketing-led), anything that looks like a diet tracker.

---

## Existing Patterns

- **Typography**: Fraunces for display (meal names, totals, cook steps), DM Mono for everything else (labels, UI chrome, data). Never swap these.
- **Colors**: `--green` is the primary accent. `--amber` for warnings/pantry. `--red` for errors only. All three should remain single-purpose.
- **Border radius**: `--radius` (16px) for cards and overlays, `--radius-sm` (10px) for inputs, buttons, smaller elements.
- **Backgrounds**: Three depth levels — `--bg` (base), `--bg2` (cards), `--bg3` (inset/inputs). Overlays use `--bg` at full opacity; sheets use `--bg2`.
- **Text**: Three levels — `--text` (primary), `--text-dim` (secondary), `--text-muted` (tertiary/placeholders).

---

## Component Inventory

| Component | Status | Notes |
|---|---|---|
| Header (logo + week badge + budget pill) | Exists | Functioning |
| Nav tabs (week / shopping / recipes) | Exists | Functioning |
| Meal cards (This Week view) | Exists | Functioning |
| Week summary card | Exists | Functioning |
| Shopping list items + progress bar | Exists | Functioning |
| Recipe library (search + filter chips) | Exists | Functioning |
| Recipe detail view | Exists | Functioning |
| Cook mode overlay (step-through) | Exists | Functioning |
| Rating overlay (👍/👎) | Exists | Functioning |
| Bundle switcher bottom sheet | Exists | Functioning |
| Custom bundle builder overlay | Exists | Functioning |
| Recipe picker overlay | Exists | Functioning |
| Settings bottom sheet | Exists | Functioning |
| Pantry staples tag editor | Exists | Functioning |
| Exclusions tag editor | Exists | Functioning |

---

## Key Interactions

- **Tab switching**: Instant view swap; active tab underlined in green.
- **Meal card → recipe detail**: Navigates within recipes tab; back button returns to library.
- **Shopping item tap**: Toggles checked state; progress bar updates. Pantry items are dimmed, not hidden.
- **Cook mode**: Full-screen step-through; "Done ✓" triggers rating overlay.
- **Bundle switcher**: Reveals from bottom; past weeks expand on tap to show multiple plans.
- **Builder → Picker → Builder**: Two-level overlay stack (builder z:300, picker z:310). ESC or back collapses in reverse order.

---

## Responsive Behavior

Mobile-only by design (375px primary target). The app shell uses `100dvh` to respect browser chrome. Safe-area insets applied via env() tokens. No desktop breakpoints currently defined — the PWA is installed to the home screen and runs full-screen.

---

## Accessibility Requirements

- Touch targets minimum 44×44px on all interactive elements.
- Body text minimum 14px; labels/badges minimum 10px.
- All inputs must have visible focus rings (currently missing on buttons).
- Colour contrast: `--text` on `--bg2` must pass WCAG AA (currently ~8:1, passing).
- Reduced-motion: transitions should be disabled or shortened for `prefers-reduced-motion`.

---

## Out of Scope

- Desktop/tablet layouts.
- Light mode (single dark theme only; no `prefers-color-scheme` switching needed now).
- Multi-user auth (Phase 2).
- Push notifications (separate milestone).
- Internationalisation (NZ English only).
