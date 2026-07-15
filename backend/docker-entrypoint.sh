#!/usr/bin/env sh
# Container entrypoint: bring the database schema up to date, then serve.
#
# Alembic is the source of truth for the Postgres schema. Running
# `alembic upgrade head` on every start is idempotent — it applies only the
# migrations the target DB has not yet seen, and is a no-op once current.
set -e

echo "[entrypoint] Applying database migrations (alembic upgrade head)…"
alembic upgrade head

echo "[entrypoint] Starting API server…"
# WORKERS defaults to 1. If you set WORKERS>1 you MUST set a stable SECRET_KEY
# (see README) or JWTs signed by one worker will be rejected by another.
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WORKERS:-1}"
