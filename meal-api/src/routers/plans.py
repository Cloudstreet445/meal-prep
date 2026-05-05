"""Legacy /api/plan endpoints — alias to bundles."""

from fastapi import APIRouter
from routers.bundles import get_latest_bundle

router = APIRouter()


@router.get("/latest")
def get_latest_plan():
    """Legacy alias for /api/bundle/latest."""
    return get_latest_bundle()