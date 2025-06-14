# Stage 1: Build the application artifact
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

ARG BUILD_VERSION
WORKDIR /app

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
COPY . .

# This single, contiguous RUN command determines the version and builds the wheel.
RUN \
    if [ -n "$BUILD_VERSION" ]; then \
      VERSION="$BUILD_VERSION"; \
      echo "--- Using provided build version: $VERSION ---"; \
    else \
      echo "--- Resolving version from git ---"; \
      SHORT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "0000000"); \
      HIGHEST_TAG=$(git tag --list | grep -E '^v?[0-9]+\.[0-9]+(\.[0-9]+)?(\.[a-zA-Z0-9]+)?$' | sort -V -r | head -n 1); \
      if [ -z "$HIGHEST_TAG" ]; then \
        BASE_VERSION="0.0.0"; \
      else \
        BASE_VERSION=$(echo "$HIGHEST_TAG" | sed 's/^v//'); \
      fi; \
      VERSION="${BASE_VERSION}+g${SHORT_HASH}"; \
      echo "--- Resolved git version: $VERSION ---"; \
    fi && \
    \
    export HATCH_VCS_PRETEND_VERSION=$VERSION && \
    export SETUPTOOLS_SCM_PRETEND_VERSION=$VERSION && \
    python3 -m pip install --no-cache-dir hatch hatch-vcs && \
    uv sync --locked && \
    hatch build

# Stage 2: Create the final, minimal production image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

ARG INSTALL_FFMPEG=false
WORKDIR /app

RUN addgroup --gid 1000 ofscraper && \
    adduser --uid 1000 --ingroup ofscraper --home /home/ofscraper --shell /bin/sh --disabled-password --gecos "" ofscraper

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

RUN USER=ofscraper && \
    GROUP=ofscraper && \
    curl -SsL https://github.com/boxboat/fixuid/releases/download/v0.6.0/fixuid-0.6.0-linux-amd64.tar.gz | tar -C /usr/local/bin -xzf - && \
    chown root:root /usr/local/bin/fixuid && \
    chmod 4755 /usr/local/bin/fixuid && \
    mkdir -p /etc/fixuid && \
    printf "user: $USER\ngroup: $GROUP\npaths:\n  - /home/ofscraper/\n" > /etc/fixuid/config.yml

RUN uv venv
COPY --from=builder /app/dist/*.whl .

# --- REFACTORED: This RUN step now conditionally installs ffmpeg alongside the wheel ---
RUN \
    # First, install the application itself from the local wheel file.
    # We use a wildcard *.whl because the filename changes with the version.
    uv pip install *.whl -v; \
    \
    # Then, check the value of the INSTALL_FFMPEG build argument.
    if [ "$INSTALL_FFMPEG" = "true" ]; then \
      echo "--- INSTALL_FFMPEG=true. Installing pyffmpeg separately. ---"; \
      # Install pyffmpeg directly from PyPI.
      uv pip install pyffmpeg; \
    else \
      echo "--- INSTALL_FFMPEG=false. Skipping pyffmpeg installation. ---"; \
    fi && \
    \
    # Finally, clean up the wheel file after installation.
    rm *.whl

ENV PATH="/app/.venv/bin:${PATH}"
USER ofscraper:ofscraper
ENTRYPOINT ["fixuid", "-q"]
CMD ["ofscraper"]