"""Pak'nSave Meal Planner API."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .routers import bundles, recipes, shopping, plans
import time

app = FastAPI(
    title="Kai Planner API",
    description="Weekly meal planning API — bundles, recipes, shopping lists",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tailscale/home network only
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000)
    print(f"{request.method} {request.url.path} → {response.status_code} ({duration}ms)")
    return response


app.include_router(bundles.router,  prefix="/api/bundle",   tags=["Bundles"])
app.include_router(recipes.router,  prefix="/api/recipes",  tags=["Recipes"])
app.include_router(shopping.router, prefix="/api/shopping", tags=["Shopping"])
app.include_router(plans.router,    prefix="/api/plan",     tags=["Plans (legacy)"])


@app.get("/health")
def health():
    return {"status": "ok"}