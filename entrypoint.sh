#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting FastAPI application..."
python3 -m uvicorn "fastapi_app:create_app" --factory --host 0.0.0.0 --port 8000
