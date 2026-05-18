# Kai Planner

A self-hosted weekly meal planner for NZ households. Generates a $60/week dinner plan using live PAK'nSave prices, builds a deduplicated shopping list, and serves it as a mobile PWA.

## Features

- **Library-first planning** — 600+ pre-generated recipes, picked by protein variety and budget
- **Live pricing** — shopping list enriched with real PAK'nSave prices and deal flags
- **Cook mode** — step-by-step cooking overlay
- **Seasonal awareness** — winter leans toward soups/stews, summer toward salads/grills
- **Multi-user households** — magic link auth, shared plan, invite links
- **PWA** — installable on iOS/Android, works on home network + Tailscale

## Tech Stack

| Service | Language | Purpose |
|---------|----------|---------|
| `meal-api` | Python / FastAPI | REST API — bundles, recipes, shopping, auth |
| `meal-pwa` | Vanilla JS + nginx | Mobile PWA — 3-tab UI |
| `paknsave-planner` | Python | Bulk recipe generation (Claude AI) |
| `pakn-scraper` | C# / .NET 8 | Weekly PAK'nSave price scraper |
| MongoDB | — | Recipe library, pricing, user data |

## Quick Start

### Prerequisites

- Docker + Docker Compose
- MongoDB (included in compose)

### Run locally

```bash
git clone <repo>
cd meal-prep

# Copy and edit env files
cp meal-api/.env.example meal-api/.env

# Start everything
docker-compose up

# Open the app
open http://localhost:3000
```

### First login

Magic links are logged to the API console if SMTP is not configured:

```
[AUTH] Magic link for you@example.com:
  http://localhost:3000/?auth_token=<token>
```

Copy the link into your browser to sign in.

## Configuration

### meal-api `.env`

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGO_URI` | MongoDB connection string | required |
| `JWT_SECRET` | Random secret for JWT signing | `dev-secret-change-in-prod` |
| `APP_URL` | Base URL of the PWA (for magic link emails) | `http://localhost:3000` |
| `SMTP_HOST` | SMTP server host (optional) | — |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP username | — |
| `SMTP_PASS` | SMTP password | — |
| `SMTP_FROM` | From address for emails | — |

## Architecture

```
PAK'nSave website
      │  Playwright scrape
      ▼
pakn-scraper ──▶ MongoDB: paknsave-pricing
                           │
                 paknsave-planner (Claude AI)
                 ├─ Bulk generate 600+ recipes
                 └─ ──▶ MongoDB: paknsave-meals.recipes
                                  │
                              meal-api (FastAPI)
                              ├─ /api/bundle/*
                              ├─ /api/recipes/*
                              ├─ /api/shopping/*
                              ├─ /api/auth/*
                              └─ /api/household/*
                                  │  nginx proxy
                                  ▼
                               meal-pwa (nginx)
                               3 tabs: This Week · Shopping · Recipes
```

## Deployment (homelab / TrueNAS)

```bash
# Build and push all images
DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock" DOCKER_CONFIG=/tmp \
  ./build-and-push.sh

# Then restart containers from TrueNAS UI
```

## Development

```bash
# Run API with hot-reload
cd meal-api
pip install -r requirements.txt
MONGO_URI=... uvicorn src.main:app --reload

# Run tests
pytest tests/

# Serve PWA locally
cd meal-pwa/static
python3 -m http.server 3000
```

## License

MIT — see [LICENSE](LICENSE)
