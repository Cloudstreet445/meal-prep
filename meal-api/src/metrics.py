"""Read-only product metrics.

Two sources, deliberately:
  * Query-derived — counts that already live in operational collections
    (signups, active households, plan volume). No event tracking needed.
  * Event-derived — the signup→first-plan funnel and plan-gen health, which
    need the ``events`` collection populated by analytics.track.

Every function takes ``db`` (the meals DB) so it's test-patchable and has no
import-time side effects. These are safe to expose behind an admin-only
endpoint later, or run from scripts/metrics.py.
"""

from datetime import datetime, timedelta


def _since(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=days)


# ── Query-derived (no events required) ──────────────────────────────

def signups(db, days: int = 30) -> int:
    """New users registered in the last ``days``."""
    return db["users"].count_documents({"createdAt": {"$gte": _since(days)}})

def active_users(db, days: int = 7) -> int:
    """Users seen (any authenticated request) in the last ``days``."""
    return db["sessions"].count_documents({"lastSeenAt": {"$gte": _since(days)}})

def plans_generated(db, days: int = 7) -> int:
    """Bundles created in the last ``days`` (the core weekly loop)."""
    return db["bundles"].count_documents({"createdAt": {"$gte": _since(days)}})

def total_users(db) -> int:
    return db["users"].count_documents({})

def total_households(db) -> int:
    return db["households"].count_documents({})


# ── Event-derived ───────────────────────────────────────────────────

def activation_rate(db, days: int = 30, window_days: int = 7) -> dict:
    """Of users who registered in the lookback window, what fraction generated
    their first plan within ``window_days`` of registering.

    This is the single best health metric: did new users reach the "aha" moment.
    Returns counts so the caller can render a rate without dividing by zero.
    """
    registered = list(db["events"].find(
        {"event": "user_registered", "ts": {"$gte": _since(days)}},
        {"userId": 1, "ts": 1, "_id": 0},
    ))
    activated = 0
    for r in registered:
        cutoff = r["ts"] + timedelta(days=window_days)
        if db["events"].count_documents({
            "event": "plan_generated",
            "userId": r["userId"],
            "ts": {"$gte": r["ts"], "$lte": cutoff},
        }, limit=1):
            activated += 1
    cohort = len(registered)
    return {
        "cohort": cohort,
        "activated": activated,
        "rate": round(activated / cohort, 3) if cohort else None,
        "windowDays": window_days,
    }

def plan_generation_health(db, days: int = 7) -> dict:
    """Plan-gen outcomes over the last ``days``: succeeded (full 5 meals),
    degraded (3–4 meals — budget pressure), and failed (couldn't build)."""
    succeeded = db["events"].count_documents(
        {"event": "plan_generated", "props.degraded": False, "ts": {"$gte": _since(days)}})
    degraded = db["events"].count_documents(
        {"event": "plan_generated", "props.degraded": True, "ts": {"$gte": _since(days)}})
    failed = db["events"].count_documents(
        {"event": "plan_generation_failed", "ts": {"$gte": _since(days)}})
    attempts = succeeded + degraded + failed
    return {
        "succeeded": succeeded,
        "degraded": degraded,
        "failed": failed,
        "attempts": attempts,
        "failureRate": round(failed / attempts, 3) if attempts else None,
    }


def summary(db) -> dict:
    """Headline dashboard — everything in one call."""
    return {
        "generatedAt": datetime.utcnow().isoformat(),
        "totals": {"users": total_users(db), "households": total_households(db)},
        "signups30d": signups(db, 30),
        "activeUsers7d": active_users(db, 7),
        "plansGenerated7d": plans_generated(db, 7),
        "activation": activation_rate(db, days=30, window_days=7),
        "planHealth7d": plan_generation_health(db, 7),
    }
