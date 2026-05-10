# Meal PWA Docs Index

## Why These Docs Exist
This folder is the implementation contract for product behavior, UI consistency, and technical architecture.  
Engineers and agents should treat these files as required context before making non-trivial changes.

## Read Order
1. `AGENT_GUIDE.md` - execution rules and quality bar
2. `FLOWS.md` - user journey expectations and coupling points
3. `UI.md` - layout/menu/component conventions
4. `ARCHITECTURE.md` - data boundaries, state ownership, and API usage

## When to Update Which Doc
- Update `FLOWS.md` when user journeys or flow outcomes change.
- Update `UI.md` when component behavior/layout conventions change.
- Update `ARCHITECTURE.md` when state ownership, integration boundaries, or runtime structure changes.
- Update `AGENT_GUIDE.md` when development process expectations change.

## Mandatory Rule
If code behavior changes and docs are not updated in the same change, the change is incomplete.
