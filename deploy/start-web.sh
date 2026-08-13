#!/bin/sh
set -eu
alembic upgrade head
exec gunicorn --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 30 --graceful-timeout 20 --access-logfile - 'mldsafail.web.app:create_app()'
