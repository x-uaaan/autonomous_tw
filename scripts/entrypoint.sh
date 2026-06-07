#!/bin/bash
set -e

# Print banner
echo "🇹🇼 autonomous.tw — 資訊自主。真實可溯。"
echo "============================================"

if [ "$1" = "cron" ]; then
    echo "Starting cron daemon..."
    echo "Pipeline will run every 6 hours."

    # Start cron in foreground
    exec cron -f
elif [ "$1" = "run" ]; then
    echo "Running pipeline once..."
    shift
    exec uv run autonomous-tw "$@"
else
    echo "Usage: docker compose run autonomous-tw [cron|run] [args]"
    echo ""
    echo "  cron  — Start background scheduler (runs every 6 hours)"
    echo "  run   — Run pipeline once (pass --hours N to override window)"
    echo ""
    echo "Examples:"
    echo "  docker compose run --rm autonomous-tw run"
    echo "  docker compose run --rm autonomous-tw run --hours 48"
    echo "  docker compose up -d  (starts cron mode)"
    exec "$@"
fi