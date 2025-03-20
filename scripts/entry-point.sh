#!/bin/sh
set -x
set -e
alembic upgrade head
uvicorn one_request.app:app --host 0.0.0.0 --port 8000 --forwarded-allow-ips="*" "$@"
