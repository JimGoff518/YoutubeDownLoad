#!/bin/bash
set -e

echo "Starting Bill AI Machine (Flask)..."

exec gunicorn server:app \
    --bind "0.0.0.0:${PORT:-8080}" \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --keep-alive 65 \
    --log-level info \
    --access-logfile - \
    --error-logfile -
