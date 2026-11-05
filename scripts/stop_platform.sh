#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Stopping DataFlow Enterprise platform services..."

# Stop backend uvicorn
pkill -f "uvicorn backend.app.main:app" || true

# Stop PostgreSQL
if [ -d "$DIR/.pgdata" ]; then
    /usr/lib/postgresql/16/bin/pg_ctl -D "$DIR/.pgdata" stop -m fast || true
fi

# Stop MySQL
if [ -f "/tmp/mysql3307.pid" ]; then
    kill $(cat /tmp/mysql3307.pid) || true
fi

echo "Services stopped."
