#!/usr/bin/env bash
set -euo pipefail

log() { printf '[clepsy-entrypoint] %s\n' "$*"; }

# Assume these are provided in the environment
PUID="${CLEPSY_UID}"
PGID="${CLEPSY_GID}"

#!/usr/bin/env bash
set -euo pipefail

log() { printf '[clepsy-entrypoint] %s\n' "$*"; }

# Assume these are provided in the environment
PUID="${CLEPSY_UID}"
PGID="${CLEPSY_GID}"

# Run shared permission/user setup
/app/scripts/fix_permissions.sh



# Require shared static mount
if [ ! -d "/shared-static" ]; then
	echo "[clepsy-entrypoint] Error: /shared-static mount is required (bind or named volume)." >&2
	exit 1
fi

# Default behavior: refresh static, run migrations, start server
log "Refreshing shared static assets..."
rsync -a --delete --no-perms --no-owner --no-group /app/static/ /shared-static/

log "[prod] Running migrations"
gosu "${PUID}:${PGID}" goose up || true
log "[prod] Starting server"
exec gosu "${PUID}:${PGID}" uvicorn clepsy.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --proxy-headers \
    --forwarded-allow-ips="*"
