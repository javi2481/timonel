#!/usr/bin/env bash
# All PaddleX SPA capabilities up (no on-demand stop).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== docker compose up (all caps) =="
docker compose -f docker-compose.yml up -d --build --wait

echo "OK — open http://localhost:8000/"
echo "All default PaddleX services running; UI capas activas al boot."
