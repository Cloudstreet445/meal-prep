"""Internal product analytics — minimal, server-side, fail-safe.

We track a small set of events so we can answer the questions that actually
matter for a weekly meal planner: do new users reach the "aha" moment (generate
a plan), and is the core plan-generation loop healthy (success vs failed vs
degraded). Most other metrics (signups, active households, ratings) are already
derivable from existing collections, so they are NOT events — see metrics.py.

Design notes:
  * Events live in the ``events`` collection of the meals DB (same Mongo
    instance, no extra infra). A TTL index expires raw events after
    EVENT_TTL_DAYS so the collection self-prunes.
  * Events are pseudonymous: we store userId / householdId, never email or
    other PII, and props should be small scalar facts (counts, flags, enums).
  * ``track`` is best-effort and MUST NOT break the request it's called from —
    any failure is swallowed and logged, never raised.
"""

import logging
from datetime import datetime

_log = logging.getLogger(__name__)

EVENT_TTL_DAYS = 180

# The canonical event names. Keeping them as constants (and an allowlist) stops
# typo-duplicated event names from silently fragmenting the data.
USER_REGISTERED = "user_registered"
PLAN_GENERATED = "plan_generated"
PLAN_GENERATION_FAILED = "plan_generation_failed"

KNOWN_EVENTS = frozenset({
    USER_REGISTERED,
    PLAN_GENERATED,
    PLAN_GENERATION_FAILED,
})


def track(db, event: str, *, user_id: str | None = None,
          household_id: str | None = None, props: dict | None = None) -> None:
    """Record one analytics event. Best-effort: never raises.

    ``db`` is passed in (rather than imported) so callers use their own
    test-patchable connection, matching the rest of the codebase.
    """
    try:
        if event not in KNOWN_EVENTS:
            _log.warning("Dropping unknown analytics event %r", event)
            return
        db["events"].insert_one({
            "event": event,
            "userId": user_id,
            "householdId": household_id,
            "props": props or {},
            "ts": datetime.utcnow(),
        })
    except Exception as exc:  # analytics must never break a user request
        _log.warning("analytics track(%s) failed: %s", event, exc)
