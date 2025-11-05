FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

ENV LC_CTYPE=C.utf8
ENV UV_PROJECT_ENVIRONMENT="/venv"
ENV UV_PYTHON_PREFERENCE=system
ENV PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"

# System deps (with apt cache mounts)
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends -y \
      tzdata \
      ca-certificates \
      locales \
      sudo \
      gpg \
      curl \
      git \
      build-essential \
      gettext \
      rsync \
      wget \
      sqlite3 \
      libgl1 \
      libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Goose (db migrations)
RUN curl -fsSL https://raw.githubusercontent.com/pressly/goose/master/install.sh | sh

WORKDIR /app
ENV PORT=8000
EXPOSE 8000

# ---------- 1) Cache PROD deps (no project install) ----------
FROM base AS prod-deps
ENV ENVIRONMENT=prod
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --no-dev --no-install-project

# ---------- 2) Cache DEV deps (no project install) ----------
FROM base AS dev-deps
ENV ENVIRONMENT=dev
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --group dev --no-install-project

# ---------- 3) Builder: install project using cached dev deps ----------
FROM base AS builder
ENV ENVIRONMENT=dev
WORKDIR /app
COPY --from=dev-deps /venv /venv
COPY src/ /app/src/
COPY migrations/ /app/migrations/
COPY baml_src/ /app/baml_src/
COPY static/ /app/static/
COPY pyproject.toml uv.lock ./

# Install project into the pre-populated venv (fast due to cache)
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --group dev

# Build assets / codegen (use cached uv env)
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv run tailwindcss -i ./src/clepsy/frontend/css/app.css -o ./static/app.css
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv run baml-cli generate

# ---------- 4) Tests (optional) ----------
FROM builder AS tests
ENV ENVIRONMENT=prod
COPY tests/ /app/tests/
COPY test_images/ /app/test_images/
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv run python -m compileall src/clepsy
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv run python -m compileall tests

# ---------- 5) Production image ----------
FROM base AS production
LABEL org.opencontainers.image.description="Clepsy backend server image"
ENV ENVIRONMENT=prod
WORKDIR /app

COPY pyproject.toml uv.lock entrypoint.sh ./
COPY --from=prod-deps /venv /venv
COPY --from=builder /app/src/ /app/src/
COPY --from=builder /app/migrations/ /app/migrations/
COPY --from=builder /app/static/ /app/static/

# Install just the project against cached prod deps
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --no-dev

RUN chmod +x /app/entrypoint.sh
