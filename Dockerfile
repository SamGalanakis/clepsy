ARG APP_UID=1000
ARG APP_GID=1000

# ---------- Base toolchain (root) ----------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base
ENV DEBIAN_FRONTEND=noninteractive \
    LC_CTYPE=C.utf8 \
    UV_PROJECT_ENVIRONMENT="/venv" \
    UV_PYTHON_PREFERENCE=system \
    PATH="/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
# Reproducible installs (no upgrade)
RUN --mount=type=cache,target=/var/cache/apt,id=apt-cache,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,id=apt-lib,sharing=locked \
    mkdir -p /var/lib/apt/lists/partial && \
    apt-get update && \
    apt-get install --no-install-recommends -y \
        tzdata \
        curl build-essential sqlite3 libgl1   libglib2.0-0   libgl1-mesa-glx libglib2.0-0  gosu adduser && \
    rm -rf /var/lib/apt/lists/*
# Goose (db migrations)
RUN curl -fsSL https://raw.githubusercontent.com/pressly/goose/master/install.sh | sh

WORKDIR /app

## Deprecated static user stage removed; dynamic user handled at runtime

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
FROM base AS builder
ENV ENVIRONMENT=dev
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
## No user switch; runtime entrypoint will create and chown dynamically


# Optional compile checks
# RUN uv run python -m compileall src/clepsy

# ---------- 4) Production runtime (non-root) ----------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS production
ARG APP_UID
ARG APP_GID

ENV DEBIAN_FRONTEND=noninteractive \
    LC_CTYPE=C.utf8 \
    UV_PROJECT_ENVIRONMENT="/venv" \
    UV_PYTHON_PREFERENCE=system \
    PATH="/venv/bin:$PATH" \
    ENVIRONMENT=prod

# Minimal runtime deps only (no sudo)
RUN --mount=type=cache,target=/var/cache/apt,id=apt-cache,sharing=locked \
        --mount=type=cache,target=/var/lib/apt,id=apt-lib,sharing=locked \
    mkdir -p /var/lib/apt/lists/partial && \
    apt-get update && \
    apt-get install --no-install-recommends -y \
                tzdata ca-certificates libgomp1 locales sqlite3 rsync gosu && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

## Dynamic user creation & chown is handled at runtime inside entrypoint.sh

# Bring in venv and app
COPY --from=prod-deps /venv /venv
COPY --from=base /usr/local/bin/goose /usr/local/bin/goose
COPY pyproject.toml uv.lock entrypoint.sh ./
COPY --from=builder /app/src/ ./src/
COPY --from=builder /app/migrations/ ./migrations/
COPY --from=builder /app/static/ ./static/

RUN chmod +x /app/entrypoint.sh

# Install the project into the prebuilt venv without re-resolving deps
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv pip install --no-deps .

ENV DEBIAN_FRONTEND=
ENTRYPOINT ["/app/entrypoint.sh"]
