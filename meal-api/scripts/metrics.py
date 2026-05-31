"""Print the internal product-metrics summary.

Run from the meal-api directory (reads MONGO_URI from .env / environment):
    python scripts/metrics.py

Read-only: runs aggregations over existing collections + the analytics
``events`` collection. Safe to run against production.
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from src.database import get_db
from src import metrics


def main() -> None:
    data = metrics.summary(get_db())

    t = data["totals"]
    act = data["activation"]
    ph = data["planHealth7d"]

    def _pct(x):
        return "—" if x is None else f"{x * 100:.1f}%"

    print("─" * 48)
    print("Kai Planner — internal metrics")
    print(f"  generated: {data['generatedAt']}Z")
    print("─" * 48)
    print(f"Users (total)            {t['users']}")
    print(f"Households (total)       {t['households']}")
    print(f"Signups (30d)            {data['signups30d']}")
    print(f"Active users (7d)        {data['activeUsers7d']}")
    print(f"Plans generated (7d)     {data['plansGenerated7d']}")
    print("─" * 48)
    print(f"Activation ({act['windowDays']}d window)")
    print(f"  cohort {act['cohort']} → activated {act['activated']}  ({_pct(act['rate'])})")
    print("─" * 48)
    print("Plan generation health (7d)")
    print(f"  succeeded {ph['succeeded']} · degraded {ph['degraded']} · failed {ph['failed']}")
    print(f"  failure rate: {_pct(ph['failureRate'])}")
    print("─" * 48)
    print("\nraw JSON:")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
