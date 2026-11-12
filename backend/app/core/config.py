"""Application configuration — all values come from the environment.

Secrets are never hardcoded and never committed (see .env.example).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "commontable"
    app_env: str = "development"  # development | staging | production
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_url: str = "http://localhost:3000"

    database_url: str = (
        "postgresql+psycopg://commontable:commontable_dev@localhost:5432/commontable"
    )

    jwt_secret_key: str = "CHANGE_ME_generate_a_random_secret_per_environment"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    redis_url: str = "redis://localhost:6379/0"

    # Maps provider abstraction (spec section 8.1): "google" | "mapbox".
    maps_provider: str = "unset"
    maps_api_key: str = ""

    # Payments abstraction (spec section 14, decision D2). "stub" until a
    # marketplace-capable provider is confirmed against current docs.
    # No real money moves while the provider is "stub".
    payment_provider: str = "stub"
    payment_api_key: str = ""
    payment_webhook_secret: str = ""


settings = Settings()
