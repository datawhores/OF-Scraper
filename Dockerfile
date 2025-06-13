# Stage 1: Build the application artifact
FROM ghcr.io/astral-sh/uv:python3.11-bookworm AS builder

# Set the working directory
WORKDIR /app

# Accept version numbers as build arguments
ARG HATCH_VCS_PRETEND_VERSION=0.0.0
ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0
ENV HATCH_VCS_PRETEND_VERSION=$HATCH_VCS_PRETEND_VERSION
ENV SETUPTOOLS_SCM_PRETEND_VERSION=$SETUPTOOLS_SCM_PRETEND_VERSION

# --- FIX IS HERE ---
# Copy all project files first. This is necessary because `uv sync`
# needs the source directory (e.g., 'ofscraper/') to exist when it
# prepares the editable install of the local project.
COPY . .

# Install build tools AND all dependencies in one step.
# Hatch can now find the 'ofscraper' directory and build successfully.
RUN python3 -m pip install --no-cache-dir hatch && \
    uv sync --locked

# Build the final wheel artifact
RUN hatch build

# ---

# Stage 2: Create the final, minimal production image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm

# Create a non-root user and group
RUN addgroup --gid 1000 ofscraper && \
    adduser --uid 1000 --ingroup ofscraper --home /home/ofscraper --shell /bin/sh --disabled-password --gecos "" ofscraper

# Install and configure fixuid to manage permissions
RUN USER=ofscraper && \
    GROUP=ofscraper && \
    curl -SsL https://github.com/boxboat/fixuid/releases/download/v0.5.1/fixuid-0.5.1-linux-amd64.tar.gz | tar -C /usr/local/bin -xzf - && \
    chown root:root /usr/local/bin/fixuid && \
    chmod 4755 /usr/local/bin/fixuid && \
    mkdir -p /etc/fixuid && \
    printf "user: $USER\ngroup: $GROUP\npaths:\n  - /home/ofscraper/\n" > /etc/fixuid/config.yml

# Set the working directory for the final stage
WORKDIR /app

# Create a virtual environment
RUN uv venv

# Copy ONLY the built wheel from the builder stage
COPY --from=builder /app/dist/*.whl .

# Install the wheel into the venv and clean up the whl file in one step
RUN uv pip install *.whl && rm *.whl

# Add the virtual environment's bin directory to the PATH
ENV PATH="/app/.venv/bin:${PATH}"

# Switch to the non-root user
USER ofscraper:ofscraper

# Use fixuid to dynamically set user/group permissions on container start
ENTRYPOINT ["fixuid", "-q"]

# Set the default command to run your application
CMD ["ofscraper"]