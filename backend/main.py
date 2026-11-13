"""CommonTable backend entrypoint.

FastAPI application factory for the MVP slice (spec section 16.1): auth +
RBAC, restaurant/menu CRUD, customer ordering, restaurant dashboard,
driver workflow, manual dispatch, notifications, payments (stub) + ledger,
admin console, and the Direct2Door dashboard handoff.

Payments are a clearly labeled stub: no real money moves in the slice.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (
    admin,
    auth,
    deliveries,
    dispatch,
    drivers,
    notifications,
    orders,
    payments,
    restaurants,
    users,
    websockets,
)
from app.core.config import settings
from app.core.errors import ApiError


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "CommonTable local food-delivery platform API (MVP slice). "
            "Payments are a labeled stub: no real money moves."
        ),
        version="0.2.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return _error_response(exc.status_code, exc.code, str(exc.detail))

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        return _error_response(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return _error_response(422, "validation_error", str(exc))

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        """Liveness probe. No database or external calls."""
        return {"status": "ok", "app": settings.app_name, "env": settings.app_env}

    api = "/api/v1"
    app.include_router(auth.router, prefix=api)
    app.include_router(users.router, prefix=api)
    app.include_router(restaurants.router, prefix=api)
    app.include_router(orders.router, prefix=api)
    app.include_router(dispatch.router, prefix=api)
    app.include_router(drivers.router, prefix=api)
    app.include_router(deliveries.router, prefix=api)
    app.include_router(payments.router, prefix=api)
    app.include_router(admin.router, prefix=api)
    app.include_router(notifications.router, prefix=api)
    app.include_router(websockets.router, prefix=api)

    return app


app = create_app()
