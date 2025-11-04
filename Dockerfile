FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

# Assure UTF-8 encoding is used.
ENV LC_CTYPE=C.utf8

# Location of the virtual environment
ENV UV_PROJECT_ENVIRONMENT="/venv"
ENV UV_PYTHON_PREFERENCE=system
# Tweaking the PATH variable for easier use
ENV PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"

# Update the system and install essential packages
RUN apt-get update && \
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

RUN curl -fsSL https://raw.githubusercontent.com/pressly/goose/master/install.sh | sh

WORKDIR /app
ENV PORT=8000
EXPOSE 8000

# 1) Cache prod deps (no project install)
FROM base AS prod-deps
ENV ENVIRONMENT=prod
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Cache dev deps (no project install)
FROM base AS dev-deps
ENV ENVIRONMENT=dev
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --group dev --no-install-project

# 3) Builder: reuse dev deps; install project; build assets
FROM base AS builder
ENV ENVIRONMENT=dev
WORKDIR /app
COPY --from=dev-deps /venv /venv
COPY src/ /app/src/
COPY migrations/ /app/migrations/
COPY baml_src/ /app/baml_src/
COPY static/ /app/static/
COPY pyproject.toml uv.lock ./
# Install the project into the pre-populated venv (fast because deps are cached)

RUN uv sync --frozen --group dev

# Build frontend CSS and generate BAML artifacts via venv
RUN uv run tailwindcss -i ./src/clepsy/frontend/css/app.css -o ./static/app.css
RUN uv run baml-cli generate

# 4) Tests stage
FROM builder AS tests
ENV ENVIRONMENT=prod
COPY tests/ /app/tests/
COPY test_images/ /app/test_images/
RUN uv run python -m compileall src/clepsy
RUN uv run python -m compileall tests

# 5) Production: reuse prod deps; install only the project
FROM base AS production
LABEL org.opencontainers.image.description="Clepsy backend server image"
ENV ENVIRONMENT=prod
WORKDIR /app

COPY pyproject.toml uv.lock entrypoint.sh ./
COPY --from=prod-deps /venv /venv

COPY --from=builder /app/src/ /app/src/
COPY --from=builder /app/migrations/ /app/migrations/
COPY --from=builder /app/static/ /app/static/

# Install just the project (no dev deps); deps already present
RUN uv sync --frozen --no-dev

RUN chmod +x /app/entrypoint.sh
