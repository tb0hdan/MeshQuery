#!/usr/bin/env bash
set -euo pipefail
echo "========================================"
echo "  Malla Mesh Network Monitor"
echo "========================================"
echo ""
echo "Starting services: postgres, db-init, malla-capture, malla-web (port 8080)"
echo ""
docker compose build
docker compose up -d
echo ""
echo "Viewing logs. Press Ctrl+C to stop tailing (services keep running)."
docker compose logs -f
