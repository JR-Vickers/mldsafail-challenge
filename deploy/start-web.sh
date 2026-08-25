#!/bin/sh
set -eu

# Run migrations with retry (DB may not be ready yet)
# Use python -m to avoid shebang path issues from multi-stage build
for i in $(seq 1 10); do
    if /app/.venv/bin/python -m alembic upgrade head 2>/dev/null; then
        break
    fi
    echo "Alembic migration attempt $i failed, retrying in 2s..."
    sleep 2
done

exec /app/.venv/bin/python -m gunicorn --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 30 --graceful-timeout 20 --access-logfile - 'mldsafail.web.app:create_app()'
