#!/usr/bin/env bash
set -euo pipefail

log() { printf '[clepsy-worker-entrypoint] %s\n' "$*"; }

# Assume these are provided in the environment
PUID="${CLEPSY_UID}"
PGID="${CLEPSY_GID}"

# Run shared permission/user setup
/app/scripts/fix_permissions.sh

log "Starting Dramatiq worker..."
exec gosu "${PUID}:${PGID}" bash -lc "mkdir -p /tmp/dramatiq-prometheus && rm -rf /tmp/dramatiq-prometheus/* && uv run dramatiq clepsy.jobs.desktop clepsy.jobs.mobile clepsy.jobs.aggregation clepsy.jobs.sessions clepsy.jobs.goals clepsy.jobs.scheduler_tick clepsy.jobs.scheduled_job_dispatch --processes 4 --threads 4"
