# ---------- Base toolchain (root) ----------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base
ENV LC_CTYPE=C.utf8 \
    UV_PROJECT_ENVIRONMENT="/venv" \
    UV_PYTHON_PREFERENCE=system \
    PATH="/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
# Reproducible installs (no upgrade)
RUN --mount=type=cache,target=/var/cache/apt,id=apt-cache,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,id=apt-lib,sharing=locked \
    mkdir -p /var/lib/apt/lists/partial && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
      tzdata \
      curl build-essential sqlite3 && \
    rm -rf /var/lib/apt/lists/*
# Goose (db migrations)
RUN curl -fsSL https://raw.githubusercontent.com/pressly/goose/master/install.sh | sh

WORKDIR /app

# ---------- Base with application user (root) ----------
FROM base AS base-with-user
RUN groupadd -g 1000 appuser && \
    useradd -m -u 1000 -g 1000 appuser
RUN install -d -o appuser -g 1000 /home/appuser/.cache \
    /home/appuser/.cache/uv /var/lib/clepsy \
    /var/lib/clepsy/logs /var/lib/clepsy-caches
ENV HOME=/home/appuser

# ---------- 1) Cache PROD deps ----------
FROM base AS prod-deps
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --no-dev --no-install-project

# ---------- 2) Cache DEV deps ----------
FROM base AS dev-deps
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --group dev --no-install-project

# ---------- 3) Builder (root) ----------
FROM base-with-user AS builder
ENV ENVIRONMENT=dev
ENV HOME=/home/appuser
COPY --from=dev-deps /venv /venv
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY baml_src/ ./baml_src/
COPY static/ ./static/
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --group dev

# Assets / codegen
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv run tailwindcss -i ./src/clepsy/frontend/css/app.css -o ./static/app.css && \
    uv run baml-cli generate

# prepare writable paths for the unprivileged dev user
RUN chown -R appuser:1000 /app /venv /home/appuser
USER appuser:1000


# Optional compile checks
# RUN uv run python -m compileall src/clepsy

# ---------- 4) Production runtime (non-root) ----------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS production

ENV LC_CTYPE=C.utf8 \
    UV_PROJECT_ENVIRONMENT="/venv" \
    UV_PYTHON_PREFERENCE=system \
    PATH="/venv/bin:$PATH" \
    ENVIRONMENT=prod \
    HOME=/home/appuser

# Minimal runtime deps only (no sudo)
RUN --mount=type=cache,target=/var/cache/apt,id=apt-cache,sharing=locked \
        --mount=type=cache,target=/var/lib/apt,id=apt-lib,sharing=locked \
    mkdir -p /var/lib/apt/lists/partial && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
      tzdata ca-certificates locales sqlite3 rsync libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create unprivileged user late
RUN groupadd --gid 1000 appuser && \
    useradd  --uid 1000 --gid 1000 -m -d /home/appuser appuser

# Bring in venv and app
COPY --from=prod-deps /venv /venv
COPY --from=base /usr/local/bin/goose /usr/local/bin/goose
COPY pyproject.toml uv.lock entrypoint.sh ./
COPY --from=builder /app/src/ ./src/
COPY --from=builder /app/migrations/ ./migrations/
COPY --from=builder /app/static/ ./static/

# Prepare writable paths for the runtime user
RUN install -d -o appuser -g 1000 /var/lib/clepsy /var/lib/clepsy/logs \
    /var/lib/clepsy-caches /home/appuser/.cache /home/appuser/.cache/uv && \
    chown -R appuser:1000 /app /venv /home/appuser && \
    chmod +x /app/entrypoint.sh

USER appuser:1000

# Install the project into the prebuilt venv without re-resolving deps
RUN --mount=type=cache,target=/home/appuser/.cache/uv,id=uv-cache,uid=1000,gid=1000 \
    uv pip install --no-deps .
ENTRYPOINT ["/app/entrypoint.sh"]
