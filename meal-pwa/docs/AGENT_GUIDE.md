# Code Agent Guide (Meal PWA)

Use this guide before implementing features or refactors.

## Source of Truth
- Architecture: `docs/ARCHITECTURE.md`
- UI system: `docs/UI.md`
- Product behavior: `docs/FLOWS.md`

If implementation conflicts with docs, update docs in the same change.

## Quick Start Checklist (Every Task)
1. Read affected sections in `docs/FLOWS.md`.
2. Confirm UI conventions in `docs/UI.md`.
3. Confirm data/state boundaries in `docs/ARCHITECTURE.md`.
4. Define rollback-safe implementation plan.
5. Implement + verify + update docs.

## Implementation Priorities
1. Keep mobile UX quality high.
2. Preserve current user flows unless intentionally changing them.
3. Avoid regressions in week/bundle/shopping synchronization.
4. Keep dark/light mode and accessibility intact.
5. Keep interactions fast and understandable on small screens.

## Change Workflow
1. Identify affected flow(s) in `docs/FLOWS.md`.
2. Implement smallest safe change.
3. Validate loading, empty, and error states.
4. Update docs when behavior or UI contract changes.
5. Add/adjust tests for logic changes.

## PR/Change Summary Template
- **What changed**
- **Why it changed**
- **Affected flows**
- **Risk areas**
- **Validation done**
- **Docs updated**

## Guardrails
- Do not add one-off visual tokens; reuse existing CSS variables.
- Do not introduce UI that is desktop-first at mobile's expense.
- Do not store server-owned source-of-truth data in localStorage long-term.
- Keep API error handling user-friendly and non-blocking.
- Preserve accessible focus, tap target size, and readable contrast.
- Preserve existing endpoint contracts unless backend change is intentional and coordinated.
- Avoid coupling new features to unrelated global state variables.

## Decision Rules
- If a change impacts more than one tab, validate all impacted tabs explicitly.
- If a change introduces new persistent state, document key format and ownership.
- If a change adds UI pattern not already in docs, add it to `docs/UI.md`.
- If a change alters user sequence/expectation, update `docs/FLOWS.md`.

## Common Pitfalls to Avoid
- Breaking checked shopping state by using non-bundle-scoped keys.
- Updating one view after bundle switch but not refreshing dependent views.
- Adding hard-coded colors/spacings that bypass token system.
- Silent API failure with no user-facing fallback message.
- Introducing modal/sheet states that cannot be dismissed reliably.

## Validation Matrix
- **This Week**
  - loading/success/error render states
  - generate CTA behavior
- **Shopping**
  - item toggle behavior
  - progress math
  - pantry and deal indicators
- **Recipes**
  - search and chip filters
  - detail open/back behavior
  - rating feedback reflection
- **Overlays**
  - open/close paths
  - backdrop/escape behavior
  - keyboard and touch flow

## Definition of Done
- Feature works in primary flow and adjacent flows.
- No major visual regressions in This Week / Shopping / Recipes.
- States handled: loading, success, error, empty.
- Docs updated if behavior changed.
- Manual mobile sanity check completed for affected views.
