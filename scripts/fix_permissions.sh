#!/usr/bin/env bash
set -euo pipefail

# Assume these are provided in the environment
PUID="${CLEPSY_UID}"
PGID="${CLEPSY_GID}"

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
