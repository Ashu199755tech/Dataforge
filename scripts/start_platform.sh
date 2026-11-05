#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "=========================================================="
echo "  Starting DataFlow Enterprise Platform"
echo "=========================================================="

# 1. Start PostgreSQL (port 5433)
if ! pg_isready -h 127.0.0.1 -p 5433 >/dev/null 2>&1; then
    echo "[+] Starting PostgreSQL cluster on port 5433..."
    /usr/lib/postgresql/16/bin/pg_ctl -D "$DIR/.pgdata" -o "-p 5433 -k /tmp" -l "$DIR/.pgdata/postgres.log" start
else
    echo "[*] PostgreSQL is already running on port 5433"
fi

# 2. Start MySQL (port 3307)
if ! nc -z 127.0.0.1 3307 >/dev/null 2>&1; then
    echo "[+] Starting MySQL daemon on port 3307..."
    ~/.local/bin/my_mysqld --datadir=/tmp/mysqldata --port=3307 --socket=/tmp/mysql3307.sock --pid-file=/tmp/mysql3307.pid --log-error=/tmp/mysql3307.log --daemonize
else
    echo "[*] MySQL is already running on port 3307"
fi

# 3. Seed Metadata and start server
echo "[+] Starting DataFlow Enterprise Server on http://127.0.0.1:8000..."
export PYTHONPATH="$DIR"
./venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
