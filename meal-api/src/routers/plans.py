"""Plan endpoints — trigger generation and legacy bundle alias."""

import os
import httpx
from fastapi import APIRouter, HTTPException
from .bundles import get_latest_bundle

router = APIRouter()

PLANNER_URL = os.environ.get("PLANNER_URL", "http://paknsave-planner:5001")


@router.get("/latest")
def get_latest_plan():
    """Legacy alias for /api/bundle/latest."""
    return get_latest_bundle()


@router.post("/generate")
def generate_plan():
    """Trigger the planner service to generate a new meal plan."""
    try:
        resp = httpx.post(f"{PLANNER_URL}/generate", timeout=180.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Planner service unavailable")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Plan generation timed out")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=e.response.text)