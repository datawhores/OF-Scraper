# syntax=docker/dockerfile:1.7-labs
# Stage 1: Build the application artifact
FROM ghcr.io/astral-sh/uv:0.13.5-python3.15-trixie-slim AS builder

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
COPY --parents pyproject.toml uv.lock README.md .git ofscraper plugins.py .

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
    echo "Build OF-SCRAPER with ${VERSION}" && \

    python3 -m pip install --no-cache-dir hatch hatch-vcs && \
    uv sync --locked && \
    hatch build


# Static FFmpeg for non-amd64 images (see STEP 2b), pinned by digest.
FROM mwader/static-ffmpeg:7.1.1@sha256:11a44711684c0b9f754c047dcd64235b8b52deab251bd0e0a86f22faa160749c AS static-ffmpeg

# Stage 2: Create the final, minimal production image
FROM ghcr.io/astral-sh/uv:0.13.5-python3.15-trixie-slim
WORKDIR /app

# Configure uv's venv and cache location.
ENV VIRTUAL_ENV="/app/.venv"
ENV UV_CACHE_DIR="/app/.uv_cache"
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
# Save into the mounted data folder. Set here as well as in the entrypoint
# because `docker compose exec` doesn't run the entrypoint.
ENV OFSC_SAVE_PATH_DEFAULT="/home/ofscraper/data"

# >>> CORRECTED STEP 1: Install build dependencies, then pyffmpeg, then clean up <<<
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    # Install pyffmpeg and dependencies
    && uv venv && uv pip install pyffmpeg \
    # Clean up the build tools immediately
    && apt-get purge -y --auto-remove build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    # Final cleanup (static timestamps)
    && find "${VIRTUAL_ENV}" -print0 | xargs -0 touch -h -d '2025-01-01T00:00:00Z' \
    && find "${UV_CACHE_DIR}" -print0 | xargs -0 touch -h -d '2025-01-01T00:00:00Z'
# >>> END CORRECTED STEP 1 <<<
# STEP 2: Install all OS-level dependencies in a single layer.
# (This step remains the same, installing gosu)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gosu \
    && rm -rf /var/lib/apt/lists/*
# STEP 2b: A static FFmpeg release for non-amd64 images. pyffmpeg only ships
# x86_64 binaries, so on arm64 its ffmpeg fails with 'Exec format error' and
# get_ffmpeg() falls back to this one on PATH. amd64 keeps using pyffmpeg's,
# which get_ffmpeg() finds first, so it isn't copied there.
ARG TARGETARCH
RUN --mount=type=bind,from=static-ffmpeg,source=/,target=/static-ffmpeg \
    if [ "$TARGETARCH" != "amd64" ]; then \
        cp /static-ffmpeg/ffmpeg /static-ffmpeg/ffprobe /usr/local/bin/; \
    fi
# STEP 3: Copy entrypoint scripts and make them executable.
COPY --chmod=755 ./scripts/entry/. /usr/local/bin/entry/

# STEP 4: Copy and install the ofscraper wheels into the venv.
COPY --from=builder /app/dist/*.whl .
RUN \
    WHEEL_FILE=$(ls *.whl) && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential libyaml-dev libyaml-0-2 && \
    uv pip install "${WHEEL_FILE}[ffmpeg]" -v && \
    rm "${WHEEL_FILE}" && \
    # PyYAML has no 3.15 wheel; libyaml-dev lets it build its C extension.
    # libyaml-0-2 was installed explicitly, so --auto-remove keeps it.
    apt-get purge -y --auto-remove build-essential libyaml-dev && \
    rm -rf /var/lib/apt/lists/*
# A home that any UID can write to, for containers started with --user
# (pyffmpeg and other caches live under $HOME).
RUN mkdir -p /home/ofscraper && chmod 1777 /home/ofscraper
USER root 
ENTRYPOINT ["/usr/local/bin/entry/entrypoint.sh"]
CMD ["ofscraper"]