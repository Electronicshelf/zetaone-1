#!/usr/bin/env bash
# Local full check: PostgreSQL (Docker) → schema → migrations → pytest
# Prerequisites: Docker Desktop running, Python env with dev deps (pip install -e ".[dev]")
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CONTAINER_NAME="${ZATAONE_PG_CONTAINER:-zataone-postgres}"
PG_PORT="${ZATAONE_PG_PORT:-5433}"
export DATABASE_URL="${DATABASE_URL:-postgresql://zataone:zataone@127.0.0.1:${PG_PORT}/zataone}"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop, then run this script again."
  exit 1
fi

if ! docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  echo "Starting PostgreSQL container $CONTAINER_NAME on port $PG_PORT..."
  docker run --name "$CONTAINER_NAME" \
    -e POSTGRES_DB=zataone \
    -e POSTGRES_USER=zataone \
    -e POSTGRES_PASSWORD=zataone \
    -p "${PG_PORT}:5432" \
    -d postgres:15
else
  if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "Starting existing container $CONTAINER_NAME..."
    docker start "$CONTAINER_NAME"
  fi
fi

echo "Waiting for Postgres..."
for i in $(seq 1 30); do
  if docker exec "$CONTAINER_NAME" pg_isready -U zataone -d zataone >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [[ "$i" -eq 30 ]]; then
    echo "Postgres did not become ready in time."
    exit 1
  fi
done

echo "Creating tables (SQLAlchemy)..."
python -c "from zataone.storage.database import create_all_tables; create_all_tables(); print('OK')"

if [[ -d migrations ]]; then
  echo "Applying SQL migrations..."
  for f in migrations/add_idempotency_key.sql migrations/add_violations_table.sql migrations/add_evidence_violation_link.sql; do
    if [[ -f "$f" ]]; then
      docker exec -i "$CONTAINER_NAME" psql -U zataone -d zataone -v ON_ERROR_STOP=1 < "$f"
    fi
  done
fi

echo "Running pytest (excluding heavy real-OCR test)..."
pytest tests/ -v --ignore=tests/test_zataone_pipeline_real_ocr.py

echo "Done. DATABASE_URL=$DATABASE_URL"
