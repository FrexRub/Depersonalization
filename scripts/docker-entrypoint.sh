#!/bin/sh
set -eu

python /app/scripts/download_model.py
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log

