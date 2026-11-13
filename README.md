# CommonTable

A local food-delivery network for independent restaurants: restaurant-direct
menu prices plus a clearly disclosed delivery fee, fulfilled by a shared local
driver network. **Direct2Door** is the restaurant-direct delivery service
within CommonTable — delivery offered from a restaurant's own website or
ordering channel, with the restaurant keeping its menu pricing and customer
relationship.

> **Status: MVP slice implemented (spec §16.1).**
> The smallest end-to-end slice is built: auth + RBAC, restaurant/menu
> CRUD, customer ordering (pickup + Standard), restaurant dashboard
> actions, driver workflow, manual dispatch, notifications, payments
> (labeled stub) + ledger, admin console, and the Direct2Door dashboard
> handoff, with WebSocket live updates. One pilot zone (Denton), one demo
> restaurant, no batching, no real payments.
>
> **Payments are a labeled stub: no real money moves.** The payment
> provider is `stub` until decision D2 (payment provider) is confirmed.
> Nothing in the slice claims a payment was processed.
>
> **Working names:** "CommonTable" and "Direct2Door" are provisional and have
> not been cleared for trademark, business-name, domain, or app-store use.
> All fees, volumes, and contribution figures in the spec are illustrative
> hypotheses from the blueprint, not approved prices or a forecast.
> This repo is not legal, tax, insurance, or financial advice.

## Documentation

- **Phase 1 production specification** (product requirements, user stories,
  role permissions, order lifecycle, architecture, ERD, API contract, key
  risks, open decisions, proposed MVP slice):
  `../goals/launch-commontable-as-a-live-food-delivery-platform/files/phase-1-production-spec.md`
- **Source blueprint:** `../user/files/CommonTable_Direct2Door_Startup_Blueprint.docx`
  (v1.0, November 2026). The blueprint is the source of truth; the spec
  grounds every number and rule in it.

## Repository layout

```
commontable/
├── backend/                 # Python FastAPI API (MVP slice)
│   ├── app/
│   │   ├── api/             # Routers (one per service module)
│   │   ├── core/            # Config, security, auth deps, errors
│   │   ├── db/              # Engine, session, base, geometry type
│   │   ├── models/          # SQLAlchemy models (per spec §9 ERD)
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   └── services/        # Business logic (order, pricing, ledger, ...)
│   ├── alembic/             # Database migrations (0001 initial schema)
│   ├── scripts/             # seed.py, import_denton_restaurants.py
│   ├── tests/               # pytest suite (SQLite)
│   ├── main.py              # App entrypoint (factory)
│   └── requirements.txt
├── frontend/                # Next.js / React (placeholder)
│   └── app/                 # App Router placeholder
├── docs/                    # ADRs and runbooks (added as decisions land)
├── docker-compose.yml       # PostgreSQL + PostGIS for local development
├── .env.example             # Environment template (no secrets, no real keys)
└── README.md
```

## Stack (per spec §8)

| Layer | Choice |
|---|---|
| Web (customer, restaurant, admin) | Next.js / React (TypeScript) |
| Driver app | React Native (recommended; see spec §8.2) |
| Backend | Python FastAPI |
| Database / geo | PostgreSQL + PostGIS |
| Realtime | WebSockets; push via FCM / APNs |
| Maps | Provider abstraction (Google Maps or Mapbox) |
| Dispatch optimization | Deterministic rules first, OR-Tools second |
| Payments | Marketplace-capable provider behind an abstraction (Stripe Connect is the leading candidate — confirm against current docs) |
| Cloud | AWS or Google Cloud (to be decided) |

## Local setup

Prerequisites: Docker + Docker Compose (for PostgreSQL + PostGIS),
Python 3.12+, Node.js 20+.

```bash
# 1. Environment (placeholders only — no real keys)
cp .env.example .env

# 2. Database (PostgreSQL + PostGIS)
docker compose up -d db

# 3. Backend — one setup path
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL="postgresql+psycopg://commontable:commontable_dev@localhost:5432/commontable" alembic upgrade head
python scripts/seed.py          # Denton zone, pricing, Demo Diner, demo users
uvicorn main:app --reload       # http://localhost:8000/health

# 4. Frontend
cd frontend
npm install
npm run dev                     # http://localhost:3000
```

Without Docker, the backend also runs against SQLite for local checks
(tests do this): set `DATABASE_URL="sqlite:///./dev.db"`, create the
tables with the app's models, then run the seed script. Migrations
target PostgreSQL + PostGIS; SQLite is for tests and local smoke checks
only, and no test depends on PostGIS functions.

### Demo credentials (seeded by `scripts/seed.py`, password `Demo1234!`)

| User | Role |
|---|---|
| `customer@demo.commontable.local` | customer |
| `owner@demo.commontable.local` | restaurant_owner (Demo Diner) |
| `staff@demo.commontable.local` | restaurant_staff (Demo Diner) |
| `driver@demo.commontable.local` | driver (approved) |
| `dispatch@demo.commontable.local` | dispatcher |
| `admin@demo.commontable.local` | admin |

The seed script is idempotent (safe to re-run) and never runs on startup.
The demo restaurant is **Demo Diner (Denton Pilot)** — clearly demo-named,
one location, one menu, 6 items (one unavailable).

### Denton restaurant census import

```bash
cd backend
python scripts/import_denton_restaurants.py --path ../data/denton-restaurants.json
python scripts/import_denton_restaurants.py --path ../data/denton-restaurants.sample.json --dry-run
```

The importer upserts restaurants idempotently keyed by Google Maps
`place_id` and prints created / updated / skipped counts. Imported
restaurants get status `prospect` and source `census`: they are unclaimed,
not onboarded, not orderable, and visible only in the admin console with a
clear "unclaimed, not a partner" label. They never appear in customer
ordering. `data/denton-restaurants.sample.json` (4 entries, clearly sample
data) exists to verify the importer. The real census file
`data/denton-restaurants.json` (288 Denton restaurants from a Google Maps
census, plus `denton-restaurants.csv` and the coverage report
`denton-restaurants-README.md`) ships in this repo as seed data for the
prospect pipeline only — these restaurants are not partners.

### Tests

```bash
cd backend
python -m pytest tests/ -q        # SQLite via conftest DATABASE_URL override
```

The suite covers the full order loop (Standard + pickup), ledger balance,
checkout snapshot immutability, RBAC, idempotency, the census importer,
refunds, dispatch decline/override, auth, and WebSocket channels.

## Engineering rules (from the blueprint §16)

- Do not generate fake production integrations or claim a payment was
  processed when it was not.
- Use environment variables for secrets; never hardcode credentials.
- Include input validation, authorization checks, error handling, audit
  logs, and automated tests.
- Include seed data and a local development setup.
- Document assumptions and unresolved decisions.
- Keep business rules configurable rather than scattered through UI code.
- Build a working vertical slice before adding optional features.

## What is NOT built yet

Deliberately excluded from the MVP slice (spec §16.1): Saver and Express
fulfillment (the API rejects them), pooled/batch dispatch and OR-Tools
optimization, the React Native driver app, a real payment provider
(abstraction + stub only, until decision D2), POS integrations, SaaS
billing, loyalty/ads/recommendations, group ordering, ML dispatch, and
multi-zone support. Direct2Door ships as the dashboard handoff only — no
quote endpoint and no API/webhook intake in this slice.

## Deploying (Render + Supabase, free tier)

- Backend: Render Blueprint (`render.yaml`) — free web service
  `commontable-api`. Set `DATABASE_URL` to the Supabase session-pooler
  connection string and `JWT_SECRET_KEY` to a long random secret at deploy
  time. The start command runs migrations, the demo seed, and the Denton
  census import (all idempotent) before starting uvicorn. Free services
  sleep after 15 minutes idle and take about a minute to wake.
- Database: Supabase free project (500 MB). Enable the PostGIS extension
  (Dashboard -> Database -> Extensions); the Alembic migration also runs
  `CREATE EXTENSION IF NOT EXISTS postgis`. Free projects pause after 7
  days of inactivity; resume from the Supabase dashboard.
- Frontend: Vercel project `commontable` (root `frontend`). Set
  `NEXT_PUBLIC_API_URL` to the Render service URL (for example
  `https://commontable-api.onrender.com`) and redeploy. The frontend reads
  it at build time.
