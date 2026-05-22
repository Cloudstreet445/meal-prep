# Kai Planner — Project Context for Claude Code

## What This Is
A weekly meal planning app for New Zealand households. Scrapes live prices from Pak'nSave, generates budget-aware meal plans, and tracks shopping. Multi-user with households, sessions, JWT auth.

---

## Architecture — 4 Services

| Service | Stack | Purpose |
|---------|-------|---------|
| `meal-api/` | FastAPI + PyMongo | REST API, auth, plan gen, shopping, households |
| `meal-pwa/` | nginx + vanilla JS (no framework) | SPA served as static files |
| `paknsave-scraper/` | Python | Scrapes Pak'nSave product prices into MongoDB |

MongoDB collections: `users`, `households`, `sessions`, `recipes`, `bundles`, `magic_tokens`, `password_reset_tokens`, `pantry_items`

---

## Deployment — TrueNAS (self-hosted, home server)

**NOT Railway. NOT Vercel. NOT Oracle. Self-hosted on TrueNAS.**

- `docker-compose.yml` in repo root is the deploy mechanism
- Services: `api`, `pwa`, `mongo` containers
- SSH to TrueNAS server to deploy: pull, rebuild, `docker-compose up -d`
- `meal-api/.env` is **gitignored** — must be maintained manually on the TrueNAS server via SSH

### Environment variables (`meal-api/.env`)
```
MONGO_URI=mongodb://paknsave_app:letmein@192.168.1.85:27017/paknsave-meals?authSource=admin
JWT_SECRET=<strong secret — never the dev placeholder>
APP_URL=https://<truenas-ip-or-domain>
```
In docker-compose, `MONGO_URI` is overridden inline to use the Docker network hostname `mongo` instead of `192.168.1.85`.

---

## Key Conventions

### Backend (`meal-api/`)
- All routers in `src/routers/`. Import pattern: `from ..database import get_db`, `from ..auth_utils import require_user`
- Rate limiting via `slowapi` — single shared `Limiter` instance in `src/limiter.py`. Import it there; don't create a new one in routers.
- Auth: JWT in httponly cookie `access_token`. `require_user` = auth required, `get_current_user` = optional.
- `JWT_SECRET` must be set — `auth_utils.py` raises `ValueError` at startup if missing.
- CORS: `allow_origins=[APP_URL]` only. Never `"*"`.

### Frontend (`meal-pwa/static/`)
- **No framework** — vanilla JS, no build step, no npm.
- `app.js` is one large file (~4000+ lines). Functions are global.
- CSS custom properties: `--accent` (#22c55e green), `--success`, `--warning`, `--danger`, `--surface-raised`, `--surface-sunken`, `--bg`, `--bg2`, `--text`, `--text-muted`.
- XSS protection: use `_esc(str)` for any user/API data interpolated into `innerHTML`. Or use `textContent`.
- Non-JSON API responses: use `_safeJson(res)` instead of bare `res.json()` in auth flows.
- Empty states: use `_emptyState({icon, title, subtitle, ctaLabel, ctaFn})` helper — don't hand-write empty state HTML.
- `apiFetch(path, opts)` wraps all API calls — handles 401 redirect to `/login`.

### HTML/CSS rule
Every HTML addition needs a corresponding CSS rule. Don't add elements without styling them.

---

## Active Linear Projects

| Project | ID |
|---------|----|
| Phase 3 — Polish & Mobile | `f0b39601-afa7-495d-8c3a-fff1251de5a3` |
| Phase 2 — Multi-User | `4416d266-57b0-4700-9b71-985b337b59b9` |
| Team | `c89c8c24-1858-45b9-b637-a3f1c0299e01` |

Ticket naming: `MEA-NNN`. Completed sprint work through MEA-168.

---

## What's Already Built (don't rebuild)
- Auth system: register, login, logout, forgot/reset password, magic link (legacy), sessions list/revoke
- Side nav drawer + bottom tab nav (This Week / Shopping / Recipes)
- Cook mode with step-by-step instructions and cooking term highlights
- Recipe detail with ingredients (pantry-aware), method steps as cards, cost breakdown
- Substitution overlay
- Household management + member invites
- Pantry tracking
- Bundle history with read-only viewing (`_viewingBundleId` in localStorage — doesn't change DB active flag)
- Pull-to-refresh on all tabs
- Skeleton loading screens (replace spinners)
- Empty states and error banner throughout
- Auth pages: radial gradient bg, icon inputs, pill button, card on wide screens
- Settings auto-save on blur
- Floating Action Button (FAB) — generate plan on Week tab, add item on Shopping tab
- Single meal swap (⇄ button on meal cards)
- Rating-aware plan generation (👎 recipes excluded)
- Shopping list: sticky category headers, live running total, checked items sink, ad-hoc items
- PWA manifest with SVG + PNG icons
- Onboarding: 3 steps (store → budget+household → ready), each skippable

---

## What's NOT Done / Known Issues
- Oracle server `.env` may need `JWT_SECRET` added manually after the secure-secret update
- Shopping list unit conversion (MEA-129) — culinary units (cloves, cups) still map incorrectly to store prices, producing absurd costs
- Pak'nSave scraper runs separately and needs a cron or manual trigger to refresh prices

---

## Running Locally
```bash
# API
cd meal-api && pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000

# PWA (just needs a static server)
cd meal-pwa && python3 -m http.server 3000
```
Or via docker-compose from repo root:
```bash
docker-compose up --build
```
