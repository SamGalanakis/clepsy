


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


FROM base AS builder
ENV ENVIRONMENT=dev


COPY pyproject.toml uv.lock ./
COPY src/ /app/src/
COPY migrations/ /app/migrations/
COPY baml_src/ /app/baml_src/
COPY static/ /app/static/


RUN uv sync --frozen --group dev



RUN uv run tailwindcss -i ./src/clepsy/frontend/css/app.css -o ./static/app.css
RUN baml-cli generate


FROM builder AS tests
ENV ENVIRONMENT=prod
COPY tests/ /app/tests/
COPY test_images/ /app/test_images/
RUN uv run python -m compileall tests


FROM base AS production
LABEL org.opencontainers.image.description="Clepsy backend server image"

ENV ENVIRONMENT=prod

COPY pyproject.toml uv.lock entrypoint.sh ./

COPY --from=builder /app/src/ /app/src/
COPY --from=builder /app/migrations/ /app/migrations/
COPY --from=builder /app/static/ /app/static/

RUN uv sync --no-dev --frozen

RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
