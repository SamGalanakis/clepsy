#!/bin/sh
set -eu

log() {
	printf '[clepsy-entrypoint] %s\n' "$*"
}

refresh_shared_static() {
	if [ ! -d "/shared-static" ]; then
		return
	fi

	log "Refreshing shared static assets..."
	rsync -a --delete /app/static/ /shared-static/
	log "Shared static assets updated."
}

refresh_shared_static

# Run database migrations
log "Running database migrations..."
goose up

# Start the application
log "Starting Clepsy backend..."
exec uvicorn clepsy.main:app \
	--host 0.0.0.0 \
	--port 8000 \
	--workers 2 \
	--proxy-headers \
	--forwarded-allow-ips="*"
