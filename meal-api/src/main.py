"""Pak'nSave Meal Planner API."""

import os
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .limiter import limiter
from .routers import bundles, recipes, shopping, plans, settings, substitutions, enhancements, auth, pantry, households

import logging as _logging
_APP_URL = os.getenv("APP_URL", "http://localhost")
if _APP_URL == "http://localhost":
    _logging.getLogger(__name__).warning(
        "APP_URL not set — CORS will only allow http://localhost; set APP_URL=https://your-domain in .env"
    )

app = FastAPI(
    title="Kai Planner API",
    description="Weekly meal planning API — bundles, recipes, shopping lists",
    version="0.1.0"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[_APP_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Invalid request"})


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
app.include_router(settings.router,       prefix="/api/settings",       tags=["Settings"])
app.include_router(substitutions.router,   prefix="/api/substitutions",  tags=["Substitutions"])
app.include_router(enhancements.router,   prefix="/api/enhancements",   tags=["Enhancements"])
app.include_router(auth.router,           prefix="/api/auth",            tags=["Auth"])
app.include_router(pantry.router,         prefix="/api/pantry",          tags=["Pantry"])
app.include_router(households.router,     prefix="/api/household",       tags=["Household"])


@app.get("/health")
def health():
    return {"status": "ok"}
