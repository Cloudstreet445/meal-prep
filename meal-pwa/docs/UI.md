# Meal PWA UI Guide

## Design Intent
- Mobile-first experience for fast weekly meal planning.
- Calm, high-contrast interface with clear hierarchy and low cognitive load.
- One primary action per screen; secondary actions in sheets/overlays.

## Core Navigation
- Top-level tabs:
  - `This Week`
  - `Shopping`
  - `Recipes`
- Header utilities:
  - weekly plan switcher
  - theme toggle
  - settings
  - budget pill

## Menu and Overlay Map
- **Header row**
  - `↕ Weekly Plans`: opens bundle switcher sheet
  - theme icon: toggles dark/light theme
  - settings icon: opens settings sheet
  - budget pill: read-only budget vs estimated spend context
- **Bottom sheets**
  - Settings sheet
  - Weekly Plans sheet
  - Substitution sheet
- **Full overlays**
  - Build Plan overlay
  - Recipe Picker overlay
  - Cook Mode overlay
  - Rating overlay
  - Cooking term tooltip (floating modal-like element)

## Information Hierarchy
- `This Week`: summary -> dinners list -> generate action.
- `Shopping`: total -> progress -> item checklist.
- `Recipes`: search/filters -> list -> detail -> cook mode.

## Layout Rules
- Target viewport: phone first (`100dvh`, safe-area aware).
- Preserve sticky controls where implemented (recipe library controls).
- Keep section rhythm consistent:
  - section label
  - content block
  - optional action row
- Do not introduce desktop-only layouts that degrade mobile ergonomics.

## Layout Specifications
- Header:
  - must remain fixed visual anchor at top
  - actions grouped right, identity/context grouped left
- Tab bar:
  - exactly three primary tabs unless product direction changes
  - active tab must be obvious without relying on color alone
- Main content:
  - each tab owns its own loading/error/empty states
  - vertical scroll should be per main content container, not whole document
- Sheets:
  - max height should preserve visual context and clear dismissal affordance
  - include handle + title + content + optional footer action area

## Component Rules

### Cards
- Meal cards and recipe list cards remain tappable across the full surface.
- Metadata uses compact pills and muted secondary text.
- Keep card internals vertically compact; avoid long text overflow by truncation/line-clamp rules.

### Buttons
- Primary actions use filled accent style.
- Secondary actions use subtle bordered style.
- Icon-only buttons require accessible labels.
- Dangerous/destructive actions require clear semantic treatment and confirmation when needed.

### Sheets and Overlays
- Use bottom sheets for list-selection/settings tasks.
- Use full overlays for focused workflows (cook mode, builder, picker).
- Always provide clear dismissal affordances (close icon, backdrop, escape).

### Inputs and Filters
- Search inputs should be immediate-feedback and lightweight.
- Filter chips are single-select per filter group.
- Keep chip labels short and scannable.
- Inputs in sheets should avoid layout jump when virtual keyboard opens.

## Visual System Rules
- Colors and spacing must use existing CSS custom properties.
- Reuse typography system:
  - `Fraunces` for emphasis/headings
  - `DM Mono` for UI body and controls
- Ensure dark/light parity for all new UI states.
- Keep contrast at accessible levels for text, icons, and state indicators.

## Token Usage Rules
- Always use existing variables for:
  - spacing (`--sp-*`)
  - type (`--text-*`)
  - color (`--bg*`, `--text*`, `--green*`, `--border`, etc.)
- If a new token is needed:
  - define once in token area
  - use semantically (not screen-specific naming)
  - support dark + light mode values

## Motion Rules
- Subtle, fast transitions by default.
- Avoid large choreography or blocking animation.
- Honor `prefers-reduced-motion` for new animations.
- Motion should communicate state change, not decorate without purpose.

## Accessibility Rules
- Keyboard and focus-visible support for interactive controls.
- Distinguish active/inactive/disabled states visually and semantically.
- Keep tap targets comfortably touchable on small devices.
- Avoid color-only communication for critical state.
- Ensure overlays trap intent (clear focus path and explicit close actions).
- Keep text sizes legible on small devices; avoid sub-10px body text.

## Content and Copy Style
- Action-first labels (`Generate new plan`, `Save Settings`).
- Use plain language and avoid jargon.
- Error copy should state:
  - what failed
  - what user can do next

## Interaction Consistency Rules
- Similar controls should behave identically across views:
  - back actions
  - close actions
  - primary CTA placement
  - loading affordances
- Any new interaction pattern must be added to this doc before broad reuse.

## UI QA Pass (Feature-Level)
- Verify on narrow viewport first, then wider mobile viewport.
- Verify dark/light themes for each new component state.
- Verify loading, empty, error, and success visual states.
- Verify keyboard escape and backdrop dismissal for overlays.

## UI Review Checklist (Before Merge)
- Does it preserve mobile usability?
- Does it reuse tokens/components instead of introducing one-off styles?
- Is dark mode readable and balanced?
- Are edge states covered (empty, loading, error, long content)?
- Are interactions discoverable without explanation?
