#!/bin/bash

# A best practice for scripts: exit immediately if any command fails.
set -e

# --- Default fallbacks ---
VERSION="0.0.0"
SANITIZED_VERSION="0_0_0"
LONG_HASH=$(printf '%0.s0' {1..40})

# --- Check if we are in a git repository ---
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    # We are in a git repo. Get the full commit hash.
    LONG_HASH=$(git rev-parse HEAD)

    # Find the highest version tag using version-sort logic
    HIGHEST_TAG=$(git tag --list | \
                  grep -E '^v?[0-9]+\.[0-9]+(\.[0-9]+)?(\.[a-zA-Z0-9]+)?$' | \
                  sort -V -r | \
                  head -n 1)

    # Determine the base version
    if [ -z "$HIGHEST_TAG" ]; then
        BASE_VERSION="0.0.0"
        echo "No valid version tags found. Using fallback base version: ${BASE_VERSION}"
    else
        BASE_VERSION=$(echo "$HIGHEST_TAG" | sed 's/^v//')
        echo "Highest version tag found: ${BASE_VERSION}"
    fi
    
    # The final version is JUST the base version for a clean release.
    VERSION="${BASE_VERSION}"
    SANITIZED_VERSION=$(echo "$VERSION" | sed 's/[.+]/_/g')
else
    echo "Not a git repository. Using fallback version: ${VERSION}"
fi

# Print final values to console for local execution and easy debugging
echo "Version: ${VERSION}"
echo "Sanitized Version: ${SANITIZED_VERSION}"
echo "Long Hash: ${LONG_HASH}"


# --- Environment-Specific Output ---

# This block now handles both GitHub Actions and local execution
if [ -n "$GITHUB_ENV" ] && [ -n "$GITHUB_OUTPUT" ]; then
    # GitHub Actions: Write to special files for other steps and jobs
    echo "--- GitHub Actions environment detected. Setting outputs and env vars. ---"
    
    # For subsequent steps in the same job
    echo "SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}" >> "$GITHUB_ENV"
    echo "HATCH_VCS_PRETEND_VERSION=${VERSION}" >> "$GITHUB_ENV"
    
    # For other jobs that depend on this one
    echo "VERSION=${VERSION}" >> "$GITHUB_OUTPUT"
    echo "SANITIZED_VERSION=${SANITIZED_VERSION}" >> "$GITHUB_OUTPUT"
    echo "LONG_HASH=${LONG_HASH}" >> "$GITHUB_OUTPUT"
else
    # Local Use: Export variables. This only works if the script is run with `source`.
    export SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}
    export HATCH_VCS_PRETEND_VERSION=${VERSION}
    echo "✅ Local environment variables exported. To use them, run this script with 'source'."
fi