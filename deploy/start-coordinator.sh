#!/bin/sh
set -eu

# Fix Docker socket permissions for coordinator access.
# The Docker Desktop socket on macOS is owned by the host user and not
# group-writable for the daemon group inside the container. On macOS dev
# hosts we relax the socket to 660 so the coordinator (member of daemon GID 1
# via group_add) can spawn workers.
if [ -e /var/run/docker.sock ]; then
    chmod 660 /var/run/docker.sock 2>/dev/null || true
fi

# Run migrations with retry (DB may not be ready yet)
for i in $(seq 1 10); do
    if /app/.venv/bin/python -m alembic upgrade head 2>/dev/null; then
        break
    fi
    echo "Alembic migration attempt $i failed, retrying in 2s..."
    sleep 2
done

exec /app/.venv/bin/python -m mldsafail.evaluator.coordinator
