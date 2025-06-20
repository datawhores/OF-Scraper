# Stage 1: Build the application artifact
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

ARG BUILD_VERSION
WORKDIR /app

# --- This is the ABSOLUTE ONLY essential change to fix the psutil/gcc error ---
# It installs the necessary compiler (gcc via build-essential) and Python development headers
# needed to compile Python packages like psutil, especially for non-AMD64 platforms.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/* # Clean up apt cache to keep image size down


COPY ofscraper ofscraper
COPY pyproject.toml pyproject.toml
COPY uv.lock uv.lock
COPY README.md README.md
COPY .git .git

# This entire RUN block should be kept as a single instruction, with proper '\' for newlines.
# Every line here (except the last one of the entire RUN block) MUST end with a '\'.
RUN \
    if [ -n "$BUILD_VERSION" ]; then \
      VERSION="$BUILD_VERSION"; \
    else \
      SHORT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "0000000"); \
      HIGHEST_TAG=$(git tag --list | grep -E '^v?[0-9]+\.[0-9]+(\.[0-9]+)?(\.[a-zA-Z0-9]+)?$' | sort -V -r | head -n 1); \
      if [ -z "$HIGHEST_TAG" ]; then BASE_VERSION="0.0.0"; else BASE_VERSION=$(echo "$HIGHEST_TAG" | sed 's/^v//'); fi; \
      VERSION="${BASE_VERSION}+g${SHORT_HASH}"; \
    fi && \
    export HATCH_VCS_PRETEND_VERSION=$VERSION && \
    export SETUPTOOLS_SCM_PRETEND_VERSION=$VERSION && \
    python3 -m pip install --no-cache-dir hatch hatch-vcs && \
    uv sync --locked && \
    hatch build


# # Stage 2: Create the final, minimal production image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim
ARG INSTALL_FFMPEG=false
WORKDIR /app

RUN groupadd -r ofscraper && useradd -r -g ofscraper -u 1000 -s /usr/sbin/nologin ofscraper

# Create .venv before switching user if uv needs root permissions for that,
# though `uv venv` typically works as non-root. Let's assume it can be run as the user.
RUN uv venv
COPY --from=builder /app/dist/*.whl .

# This RUN block also needs correct '\' for multi-line commands.
RUN \
    uv pip install *.whl -v; \
    \
    if [ "$INSTALL_FFMPEG" = "true" ]; then \
      uv pip install pyffmpeg==2.4.2.20; \
    fi && \
    \
    rm *.whl

COPY ./scripts/entry/entrypoint-rootless.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
#make required mounts
RUN mkdir /Data
RUN mkdir /config
RUN chown -R ofscraper:ofscraper /config
RUN chown -R ofscraper:ofscraper /Data
#make home
RUN mkdir /home/ofscraper
RUN chown -R ofscraper:ofscraper /home/ofscraper


    
# Switch to the non-root user for all subsequent instructions and when the container runs
USER ofscraper

ENV PATH "/app/.venv/bin:${PATH}"

# #copy scripts
# # Create the 'scripts' directory if it doesn't exist to ensure copy path works
# This is usually handled by the ENTRYPOINT script or the app itself
# if we are truly rootless, we don't want the user to need to mkdir /scripts as root
# Let's assume the entrypoint script is simpler now.
# We'll copy the single entrypoint file directly

# Use exec form for ENTRYPOINT for proper signal handling
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["ofscraper"]