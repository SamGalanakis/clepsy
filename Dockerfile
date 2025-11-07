# ---------- Base toolchain (root) ----------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

ENV LC_CTYPE=C.utf8 \
    UV_PROJECT_ENVIRONMENT="/venv" \
    UV_PYTHON_PREFERENCE=system \
    PATH="/venv/bin:$PATH"

# Reproducible installs (no upgrade)
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    mkdir -p /var/lib/apt/lists/partial && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
      tzdata ca-certificates locales \
      curl git build-essential gettext wget sqlite3 \
      libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Goose (db migrations)
RUN curl -fsSL https://raw.githubusercontent.com/pressly/goose/master/install.sh | sh

WORKDIR /app

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

ARG USERNAME=appuser
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd -g $USER_GID $USERNAME && useradd -m -u $USER_UID -g $USER_GID $USERNAME

# give write access where dev needs it, then switch
RUN chown -R $USERNAME:$USER_GID /app /venv
USER $USERNAME:$USER_GID


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
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    mkdir -p /var/lib/apt/lists/partial && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
      tzdata ca-certificates locales sqlite3 libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create unprivileged user late
ARG USERNAME=appuser
ARG USER_UID=1000
ARG USER_GID=${USER_UID}
RUN groupadd --gid ${USER_GID} ${USERNAME} && \
    useradd  --uid ${USER_UID} --gid ${USER_GID} -m -d /home/${USERNAME} ${USERNAME}

# Bring in venv and app
COPY --from=prod-deps /venv /venv
COPY --from=base /usr/local/bin/goose /usr/local/bin/goose
COPY pyproject.toml uv.lock entrypoint.sh ./
COPY --from=builder /app/src/ ./src/
COPY --from=builder /app/migrations/ ./migrations/
COPY --from=builder /app/static/ ./static/

# Install the project against prod deps
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --no-dev

# Permissions: only where we need writes
RUN install -d -o ${USERNAME} -g ${USER_GID} /var/lib/clepsy /var/lib/clepsy-caches && \
    chown -R ${USERNAME}:${USER_GID} /app /venv && \
    chmod +x /app/entrypoint.sh

USER ${USERNAME}:${USER_GID}
ENTRYPOINT ["/app/entrypoint.sh"]
