# syntax=docker/dockerfile:1.7-labs
# Stage 1: Build the application artifact
FROM ghcr.io/astral-sh/uv:0.7.13-python3.11-bookworm-slim AS builder

ARG BUILD_VERSION
WORKDIR /app

# --- This is the ABSOLUTE ONLY essential change to fix the psutil/gcc error ---
# It installs the necessary compiler (gcc via build-essential) and Python development headers
# needed to compile Python packages like psutil, especially for non-AMD64 platforms.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential\
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*
COPY --parents pyproject.toml uv.lock README.md .git ofscraper .

RUN \
    if [ -n "$BUILD_VERSION" ]; then \
      VERSION="$BUILD_VERSION"; \
    else \
      SHORT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "0000000"); \
      HIGHEST_TAG=$(git tag --sort=-committerdate | grep -E '^v?[0-9]+\.[0-9]+(\.[0-9]+)?([-.][a-zA-Z0-9.]+)?$' | head -n 1); \
      if [ -z "$HIGHEST_TAG" ]; then BASE_VERSION="0.0.0"; else BASE_VERSION=$(echo "$HIGHEST_TAG" | sed 's/^v//'); fi; \
      VERSION="${BASE_VERSION}+g${SHORT_HASH}"; \
    fi && \
    export HATCH_VCS_PRETEND_VERSION=$VERSION && \
    export SETUPTOOLS_SCM_PRETEND_VERSION=$VERSION && \
    echo "Build OF-SCRAPER with ${VERSION}" && \

    python3 -m pip install --no-cache-dir hatch hatch-vcs && \
    uv sync --locked && \
    hatch build


# Stage 2: Create the final, minimal production image
FROM ghcr.io/astral-sh/uv:0.7.13-python3.11-bookworm-slim
WORKDIR /app

# Configure uv's venv and cache location.
ENV VIRTUAL_ENV="/app/.venv"
ENV UV_CACHE_DIR="/app/.uv_cache"
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

# STEP 1: Create venv, install pyffmpeg and force static
# timestamps for venv & cache to avoid unnecessary layer updates.
RUN uv venv && uv pip install pyffmpeg==2.4.2.20 && \
    find "${VIRTUAL_ENV}" -print0 | xargs -0 touch -h -d '2025-01-01T00:00:00Z' && \
    find "${UV_CACHE_DIR}" -print0 | xargs -0 touch -h -d '2025-01-01T00:00:00Z'

# STEP 2: Install all OS-level dependencies in a single layer.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# STEP 3: Copy entrypoint scripts and make them executable.
COPY --chmod=755 ./scripts/entry/. /usr/local/bin/entry/

# STEP 4: Copy and install the ofscraper wheels into the venv.
COPY --from=builder /app/dist/*.whl .
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    uv pip install *.whl -v && \
    rm *.whl && \
    apt-get purge -y --auto-remove build-essential && \
    rm -rf /var/lib/apt/lists/*

USER root 
ENTRYPOINT ["/usr/local/bin/entry/entrypoint.sh"]
CMD ["ofscraper"]