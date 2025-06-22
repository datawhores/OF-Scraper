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

# STEP 1: Install ALL OS-level dependencies in a single layer.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gosu=1.14-1+b10 \
    && rm -rf /var/lib/apt/lists/*

# STEP 2: Copy scripts directly to their final destination and make them executable.
COPY --chmod=755 ./scripts/entry /usr/local/bin/entry 

# STEP 3: Set up Python environment and install all packages in one go.
RUN uv venv
COPY --from=builder /app/dist/*.whl .
RUN uv pip install *.whl pyffmpeg==2.4.2.20 && rm *.whl

ENV PATH="/app/.venv/bin:${PATH}"
USER root 
ENTRYPOINT ["/usr/local/bin/entry/entrypoint.sh"]
CMD ["ofscraper"]