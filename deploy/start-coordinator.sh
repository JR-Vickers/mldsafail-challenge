#!/bin/sh
set -eu

# Run migrations with retry (DB may not be ready yet)
if [ "${MLDSAFAIL_SKIP_MIGRATIONS:-0}" != 1 ]; then
 migrated=0
 for i in $(seq 1 10); do
    if /app/.venv/bin/python -m alembic upgrade head 2>/dev/null; then
        migrated=1; break
    fi
    echo "Alembic migration attempt $i failed, retrying in 2s..."
    sleep 2
 done
 [ "$migrated" = 1 ] || exit 1
fi

exec /app/.venv/bin/python -m mldsafail.evaluator.coordinator
