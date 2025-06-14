# Stage 1: Build the application artifact
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Set the working directory
WORKDIR /app

RUN apt-get update && apt-get install -y git
COPY . .
RUN git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' > /app/version || echo "0.0.0" > /app/version


RUN VERSION=$(cat /app/version) && \
    export HATCH_VCS_PRETEND_VERSION=$VERSION && \
    export SETUPTOOLS_SCM_PRETEND_VERSION=$VERSION && \
    echo "--- Building ofscraper with version: $VERSION ---" && \
    python3 -m pip install --no-cache-dir hatch hatch-vcs && \
    uv sync --locked && \
    hatch build

# Stage 2: Create the final, minimal production image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Create a non-root user and group
RUN addgroup --gid 1000 ofscraper && \
    adduser --uid 1000 --ingroup ofscraper --home /home/ofscraper --shell /bin/sh --disabled-password --gecos "" ofscraper

RUN apt-get update && apt-get install -y curl


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

RUN ls .
# Install the wheel into the venv and clean up the whl file in one step
RUN uv pip install *.whl -v && \
rm *.whl

# Add the virtual environment's bin directory to the PATH
ENV PATH="/app/.venv/bin:${PATH}"



# Switch to the non-root user
USER ofscraper:ofscraper

# Use fixuid to dynamically set user/group permissions on container start
ENTRYPOINT ["fixuid", "-q"]

# Set the default command to run your application
CMD ["ofscraper"]