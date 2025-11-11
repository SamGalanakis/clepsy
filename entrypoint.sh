#!/usr/bin/env bash
set -euo pipefail

log() { printf '[clepsy-entrypoint] %s\n' "$*"; }

PUID="${CLEPSY_UID:-1000}"
PGID="${CLEPSY_GID:-1000}"

# Ensure gosu exists
command -v gosu >/dev/null 2>&1 || { echo "gosu not found"; exit 1; }

# Create group/user if needed
if ! getent group "${PGID}" >/dev/null; then
	addgroup --gid "${PGID}" clepsygrp >/dev/null 2>&1 || true
fi
if ! id -u "${PUID}" >/dev/null 2>&1; then
	adduser --disabled-password --gecos "" --uid "${PUID}" --gid "${PGID}" clepsyusr >/dev/null 2>&1 || true
fi

fix_dir() {
	local d="$1"
	[ -d "$d" ] || return 0
	local want="${PUID}:${PGID}"
	local have
	have=$(stat -c '%u:%g' "$d" || echo "")
	if [ "$have" != "$want" ]; then
		chown -R "$want" "$d" || true
		chmod -R ug+rwX "$d" || true
	fi
}

# Fix common mount points and caches (include bind mounts and venv)
for d in /var/lib/clepsy /var/lib/clepsy/logs /shared-static /var/lib/clepsy-caches /app /venv /home/clepsyusr /home/clepsyusr/.cache /home/clepsyusr/.cache/uv; do
	fix_dir "$d"
done

# If arguments are provided, run them under target user and exit
if [ "$#" -gt 0 ]; then
	exec gosu "${PUID}:${PGID}" "$@"
fi

MODE="${CLEPSY_MODE:-dev}"

# Refresh shared static if present
if [ -d "/shared-static" ]; then
	log "Refreshing shared static assets..."
	rsync -a --delete --no-perms --no-owner --no-group /app/static/ /shared-static/ || true
fi

if [ "$MODE" = "prod" ]; then
	log "[prod] Running migrations"
	gosu "${PUID}:${PGID}" goose up || true
	log "[prod] Starting server"
	exec gosu "${PUID}:${PGID}" uvicorn clepsy.main:app \
		--host 0.0.0.0 \
		--port 8000 \
		--workers 2 \
		--proxy-headers \
		--forwarded-allow-ips="*"
else
	log "[dev] Server launch disabled by default; set CLEPSY_RUN_SERVER=1 to start"
	if [ "${CLEPSY_RUN_SERVER:-0}" = "1" ]; then
		exec gosu "${PUID}:${PGID}" uvicorn clepsy.main:app \
			--host 0.0.0.0 \
			--port 8000 \
			--workers 2 \
			--proxy-headers \
			--forwarded-allow-ips="*"
	fi
	exec tail -f /dev/null
fi
