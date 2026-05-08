---
name: after-linear-task
description: Run after completing any Linear issue — writes a test for the change, runs the full suite, marks the issue Done only if tests pass.
---

# After Linear Task

Every time a Linear issue is completed, follow this checklist before marking it Done.

## 1. Write a test for the change

Identify the **affected repo and module**:
- `pakn-scraper` (C#) → add a test method in `tests/MongoDBTests.cs` or `tests/UtilitiesTests.cs`
- `paknsave-planner` (Python) → add a test in the relevant `tests/test_*.py` file
- `meal-api` (Python) → add a test in the relevant `tests/test_*.py` file
- `meal-pwa` (JS) → add a test in `tests/*.test.js`

**What to test** — pick at least one of:
- The new behaviour / endpoint / calculation (happy path)
- An edge case or error condition introduced by the change
- A regression guard: "this thing that used to break no longer breaks"

Keep it minimal — one tight test is better than zero.

## 2. Run the full test suite

Run all tests from the repo root:

```bash
/Users/blake/code/meal-prep/run_tests.sh
```

Or per-repo if faster iteration is needed:

| Repo | Command (run from that repo's directory) |
|------|------------------------------------------|
| pakn-scraper | `dotnet test tests/` |
| paknsave-planner | `python -m pytest tests/ -q` |
| meal-api | `python -m pytest tests/ -q` |
| meal-pwa | `npx vitest run` |

## 3. Fix failures before marking Done

- If your new test fails → fix the implementation or the test
- If an **existing** unrelated test fails → it was likely broken before (check `git blame`)
  - If it's a pre-existing failure, note it in the Linear comment and continue
  - If you broke it, fix it

## 4. Mark the issue Done in Linear

Only call `mcp__claude_ai_Linear__save_issue` with `status: Done` **after** the test suite passes (or after documenting any pre-existing failures).

## What counts as a good test

- Tests the **behaviour** changed by this issue, not the internal implementation
- Does not require a real MongoDB / network connection (use mocks / mongomock / EphemeralMongo)
- Runs in under 2 seconds
- Has a name that reads like a sentence: `test_proteins_on_special_includes_chicken_on_special`
