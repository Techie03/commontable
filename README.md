# CommonTable

A local food-delivery network for independent restaurants: restaurant-direct
menu prices plus a clearly disclosed delivery fee, fulfilled by a shared local
driver network. **Direct2Door** is the restaurant-direct delivery service
within CommonTable — delivery offered from a restaurant's own website or
ordering channel, with the restaurant keeping its menu pricing and customer
relationship.

> **Status: Phase 1 — specification + structure-only scaffold.**
> The product and technical specification is complete. No MVP implementation
> has been built. Per the blueprint's master prompt, the smallest end-to-end
> MVP slice is proposed in the spec and requires approval before any
> implementation code is generated.
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
├── backend/                 # Python FastAPI API (skeleton only)
│   ├── app/
│   │   ├── api/             # Routers (one per service module)
│   │   ├── core/            # Config, security, logging
│   │   ├── db/              # Engine, session, base
│   │   ├── models/          # SQLAlchemy models (per spec §9 ERD)
│   │   └── services/        # Business logic (identity, order, dispatch, ...)
│   ├── alembic/             # Database migrations (alembic-ready layout)
│   ├── tests/
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

Prerequisites: Docker + Docker Compose, Python 3.12+, Node.js 20+.

```bash
# 1. Environment (placeholders only — no real keys)
cp .env.example .env

# 2. Database (PostgreSQL + PostGIS)
docker compose up -d db

# 3. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload            # http://localhost:8000/health

# 4. Frontend (placeholder — no pages yet)
cd frontend
npm install
npm run dev                          # http://localhost:3000
```

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

Everything in the proposed MVP slice (spec §16) awaits approval: auth/RBAC,
restaurant/menu CRUD, customer ordering, restaurant dashboard, driver
workflow, manual dispatch, notifications, payments/ledger, admin console,
and the Direct2Door dashboard handoff. This scaffold contains only the
project structure, configuration, a health endpoint, and migration plumbing.
