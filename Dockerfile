# Stage 1: Build the application artifact
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

ARG BUILD_VERSION
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    # Add any other system-level development libraries if your app needs them, e.g., libffi-dev, libssl-dev
    && rm -rf /var/lib/apt/lists/* # Clean up apt cache to keep image size down


COPY . .

RUN \
    if [ -n "$BUILD_VERSION" ]; then \
      VERSION="$BUILD_VERSION"; \
    else \
      SHORT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "0000000"); \
      HIGHEST_TAG=$(git tag --list | grep -E '^v?[0-9]+\.[0-9]+(\.[0-9]+)?(\.[a-zA-Z0-9]+)?$' | sort -V -r | head -n 1); \
      if [ -z "$HIGHEST_TAG" ]; then BASE_VERSION="0.0.0"; else BASE_VERSION=$(echo "$HIGHEST_TAG" | sed 's/^v//'); fi; \
      VERSION="${BASE_VERSION}+g${SHORT_HASH}"; \
    fi && \
    export HATCH_VCS_PRETEND_VERSION=$VERSION && export SETUPTOOLS_SCM_PRETEND_VERSION=$VERSION && \
    python3 -m pip install --no-cache-dir hatch hatch-vcs && uv sync --locked && hatch build


# Stage 2: Create the final, minimal production image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim
ARG INSTALL_FFMPEG=false
WORKDIR /app

# Install gosu for user privilege management
RUN apt-get update && apt-get install -y gosu && rm -rf /var/lib/apt/lists/*

# Copy and set up the entrypoint script
COPY ./scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN uv venv
COPY --from=builder /app/dist/*.whl .

RUN \
    # Install the application wheel first
    uv pip install *.whl -v; \
    \
    # Conditionally install pyffmpeg as a separate package
    if [ "$INSTALL_FFMPEG" = "true" ]; then \
      uv pip install pyffmpeg; \
    fi && \
    \
    rm *.whl

ENV PATH="/app/.venv/bin:${PATH}"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["ofscraper"]