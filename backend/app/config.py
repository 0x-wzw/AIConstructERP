"""Application configuration, loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Database ────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./constructerp.db"
    cors_origins: str = "*"
    app_name: str = "AIConstructERP API"
    app_version: str = "3.1.0"

    # ── Auth ────────────────────────────────────────────────────────────
    secret_key: str = "dev-insecure-change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    seed_demo_users: bool = True

    # ── File Storage ────────────────────────────────────────────────────
    file_storage_backend: str = "local"
    file_storage_local_path: str = "./storage"
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = "constructerp"
    s3_force_path_style: bool = False
    max_upload_size_bytes: int = 500 * 1024 * 1024
    upload_chunk_size_bytes: int = 10 * 1024 * 1024

    # ── Chunked Upload ──────────────────────────────────────────────────
    # Temp directory for assembling chunks
    chunk_temp_dir: str = "./storage/chunks"
    # Max chunks per upload session
    max_chunks_per_upload: int = 1000
    # Chunk upload TTL (seconds) — incomplete uploads are cleaned up
    chunk_ttl_seconds: int = 86400

    # ── Encryption (Two-Bid Opening) ────────────────────────────────────
    # Key for encrypting financial proposals. In production, use a KMS.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str = ""
    # Path to public key for bidder-side encryption (if using asymmetric)
    encryption_public_key_path: str = ""

    # ── Async Workers ──────────────────────────────────────────────────
    # Backend: "none" (sync inline), "threadpool", or "redis" (RQ/Celery)
    async_worker_backend: str = "threadpool"
    # Redis URL for task queue (if using redis backend)
    redis_url: str = "redis://localhost:6379/0"
    # Virus scanning: "none", "clamav" (requires clamd running)
    virus_scan_backend: str = "none"
    clamav_host: str = "localhost"
    clamav_port: int = 3310
    # PDF text extraction: "none" or "pypdf"
    pdf_extraction_backend: str = "pypdf"

    # ── Cron / Scheduling ──────────────────────────────────────────────
    # Tender auto-close: check interval in seconds
    tender_auto_close_interval: int = 300  # 5 minutes
    # Tender countdown notification threshold (hours before close)
    tender_countdown_threshold_hours: int = 24


settings = Settings()
