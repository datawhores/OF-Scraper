# Stage 1: Build the application artifact
FROM ghcr.io/astral-sh/uv:0.7.13-python3.11-bookworm-slim AS builder

ARG BUILD_VERSION
WORKDIR /app

# --- This is the ABSOLUTE ONLY essential change to fix the psutil/gcc error ---
# It installs the necessary compiler (gcc via build-essential) and Python development headers
# needed to compile Python packages like psutil, especially for non-AMD64 platforms.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.9 \
    python3-dev=3.11.2-1+b1 \
    git=1:2.39.5-0+deb12u2 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock README.md .git .
COPY ofscraper ofscraper

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

# Configure uv venv location
ENV VIRTUAL_ENV="/app/.venv"
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

# Install pyffmpeg and force static timestamp to avoid unnecessary layer updates
RUN uv venv && uv pip install pyffmpeg==2.4.2.20 && \
    find "${VIRTUAL_ENV}" -print0 | xargs -0 touch -h -d '2025-01-01T00:00:00Z'

# Install gosu for user privilege management
RUN apt-get update && apt-get install -y gosu==1.14-1+b10 && rm -rf /var/lib/apt/lists/*

# Copy and set up the entrypoint scripts
COPY --chmod=755 ./scripts/entry /usr/local/bin/entry  

# Install the custom ofscraper wheels
COPY --from=builder /app/dist/*.whl .

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential=12.9 && \
    uv pip install *.whl -v && \
    rm *.whl && \
    apt-get purge -y --auto-remove build-essential && \
    rm -rf /var/lib/apt/lists/*
USER root 
ENTRYPOINT ["/usr/local/bin/entry/entrypoint.sh"]
CMD ["ofscraper"]