"""CommonTable backend entrypoint.

FastAPI application factory. Structure-only scaffold (Phase 1): only the
health endpoint exists. Routers, models, and services are added with the
approved MVP slice (see the Phase 1 production specification, section 16).
"""

from fastapi import FastAPI

from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "CommonTable local food-delivery platform API. "
            "Scaffold only — no business endpoints yet."
        ),
        version="0.1.0",
    )

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        """Liveness probe. No database or external calls."""
        return {"status": "ok", "app": settings.app_name, "env": settings.app_env}

    # Routers are registered here as the MVP slice lands, one per service
    # module (identity, restaurant/menu, order, dispatch, delivery,
    # payments/ledger, analytics, integrations). See spec section 10.

    return app


app = create_app()
