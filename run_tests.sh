#!/usr/bin/env bash
# Run all test suites across every repo. Exit non-zero if any suite fails.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
FAILED=0

run() {
    echo ""
    echo "══════════════════════════════════════════════"
    echo "  $1"
    echo "══════════════════════════════════════════════"
    shift
    if ! "$@"; then
        FAILED=1
    fi
}

run "pakn-scraper  (C# / MSTest)" \
    dotnet test "$REPO_ROOT/pakn-scraper/tests"

run "paknsave-planner  (Python / pytest)" \
    python -m pytest "$REPO_ROOT/paknsave-planner/tests" -q

run "meal-api  (Python / pytest)" \
    python -m pytest "$REPO_ROOT/meal-api/tests" -q

run "meal-pwa  (JS / Vitest)" \
    bash -c "cd '$REPO_ROOT/meal-pwa' && npx vitest run"

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "✅  All test suites passed."
else
    echo "❌  One or more test suites failed."
    exit 1
fi
