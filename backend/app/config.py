"""Application configuration, loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite for zero-setup local dev. Swap to Postgres with e.g.:
    #   DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/constructerp
    database_url: str = "sqlite:///./constructerp.db"

    # Comma-separated list of allowed CORS origins ("*" allows any).
    cors_origins: str = "*"

    app_name: str = "ConstructERP API"
    app_version: str = "0.2.0"

    # ── Auth ──────────────────────────────────────────────────────────
    # DEV DEFAULT ONLY — override with a strong random value in production:
    #   export SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')"
    secret_key: str = "dev-insecure-change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # If set, demo users (admin/pm/accounting/viewer) are seeded on first run.
    seed_demo_users: bool = True


settings = Settings()
