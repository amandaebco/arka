#!/usr/bin/env bash
# ARKA One-Command Bootstrap Script
# Automatically sets up the local environment, database containers, migrations,
# and initial synthetic dataset.

set -e

echo "🚀 [1/6] Checking prerequisites (uv, docker)..."
if ! command -v uv &> /dev/null; then
    echo "❌ Error: 'uv' is required but not installed. Install via: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Error: 'docker' is required but not running."
    exit 1
fi

echo "📋 [2/6] Environment configuration..."
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

echo "📦 [3/6] Syncing Python virtual environment..."
uv sync

echo "🐳 [4/6] Starting PostgreSQL (Apache AGE + pgvector) container..."
docker compose up -d

echo "⏳ Waiting for database to be ready..."
until docker compose exec -T db pg_isready -U arka -d arka_kg &> /dev/null; do
    sleep 1
done

echo "🗄️ [5/6] Running Alembic database migrations..."
uv run alembic upgrade head

echo "🌱 [6/6] Generating synthetic background dataset..."
uv run python -m app.synthetic.generator --reset --volume-latar

echo "✅ Environment bootstrap complete!"
echo ""
echo "To run tests: uv run pytest"
echo "To run ARKA chain: uv run python scripts/run_chain.py"
