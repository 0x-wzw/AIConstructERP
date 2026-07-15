"""Application configuration, loaded from environment / .env."""
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_secret_key() -> str:
    """Generate a random dev key if none is set, so the default isn't static."""
    return secrets.token_hex(32)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite for zero-setup local dev. Swap to Postgres with e.g.:
    #   DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/constructerp
    database_url: str = "sqlite:///./constructerp.db"

    # Comma-separated list of allowed CORS origins ("*" allows any).
    cors_origins: str = "*"

    app_name: str = "ConstructERP API"
    app_version: str = "0.5.0"

    # ── Auth ──────────────────────────────────────────────────────────
    # Auto-generated per install so no two dev instances share a key.
    # Override in production with a strong, stable value (e.g. from a
    # secrets manager) so tokens survive restarts:
    #   export SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')"
    secret_key: str = _default_secret_key()
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # If set, demo users (admin/pm/accounting/viewer) are seeded on first run.
    seed_demo_users: bool = True

    # ── File storage ─────────────────────────────────────────────────
    storage_backend: str = "local"  # local | s3
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50

    # S3 / MinIO
    s3_bucket: str = ""
    s3_key: str = ""
    s3_secret: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint: str = ""  # set to MinIO URL for local S3

    # ── AI agent ──────────────────────────────────────────────────────
    ai_provider: str = "ollama"  # openai | ollama | disabled
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"


settings = Settings()
