"""Application configuration, loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Database ────────────────────────────────────────────────────────
    # Default: SQLite for zero-setup dev. Switch to PostgreSQL for prod:
    #   DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/constructerp
    database_url: str = "sqlite:///./constructerp.db"

    # Comma-separated list of allowed CORS origins ("*" allows any).
    cors_origins: str = "*"

    app_name: str = "ConstructERP API"
    app_version: str = "0.3.0"

    # ── Auth ────────────────────────────────────────────────────────────
    # DEV DEFAULT ONLY — override with a strong random value in production:
    #   export SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')"
    secret_key: str = "dev-insecure-change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # If set, demo users (admin/pm/accounting/viewer) are seeded on first run.
    seed_demo_users: bool = True

    # ── File Storage ────────────────────────────────────────────────────
    # Backend: "local" (default) or "s3"
    file_storage_backend: str = "local"

    # Local storage: files are stored under this directory
    file_storage_local_path: str = "./storage"

    # S3 / MinIO storage
    s3_endpoint_url: str = ""           # e.g. "https://s3.amazonaws.com" or "http://localhost:9000"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = "constructerp"
    s3_force_path_style: bool = False   # True for MinIO

    # Max upload size in bytes (default: 500 MB)
    max_upload_size_bytes: int = 500 * 1024 * 1024

    # Chunked upload: chunk size in bytes (default: 10 MB)
    upload_chunk_size_bytes: int = 10 * 1024 * 1024


settings = Settings()
