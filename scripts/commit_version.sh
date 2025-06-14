#!/bin/bash

# A best practice for scripts: exit immediately if any command fails.
set -e

# --- Default fallbacks ---
VERSION="0.0.0+g0000000"
SANITIZED_VERSION="0_0_0_g0000000"
SHORT_HASH="0000000"
LONG_HASH=$(printf '%0.s0' {1..40})
COMMIT_TIMESTAMP="0000000000" # Default to 10 zeros for Unix timestamp
BASE_VERSION="0.0.0"
SANITIZED_BASE_VERSION="0-0-0"

# --- Check if we are in a git repository ---
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    SHORT_HASH=$(git rev-parse --short HEAD)
    LONG_HASH=$(git rev-parse HEAD)

    # --- CHANGED: Use Unix timestamp for COMMIT_TIMESTAMP ---
    # This provides a pure numeric, space-free, chronologically sortable timestamp.
    COMMIT_TIMESTAMP=$(git show -s --format=%ct HEAD)
    echo "Commit Timestamp (Unix): ${COMMIT_TIMESTAMP}"

    HIGHEST_TAG=$(git tag --sort=-committerdate | \
                  grep -E '^v?[0-9]+\.[0-9]+(\.[0-9]+)?([-.][a-zA-Z0-9.]+)?$' | \
                  head -n 1)

    if [ -z "$HIGHEST_TAG" ]; then
        BASE_VERSION="0.0.0"
        echo "No valid version tags found pointing to recent commits. Using fallback base version: ${BASE_VERSION}"
    else
        BASE_VERSION=$(echo "$HIGHEST_TAG" | sed 's/^v//')
        echo "Base version from newest commit tag: ${BASE_VERSION}"
    fi
    
    SANITIZED_BASE_VERSION=$(echo "$BASE_VERSION" | sed 's/[.+]/-/g')
    echo "Sanitized Base Version: ${SANITIZED_BASE_VERSION}"

    VERSION="${BASE_VERSION}+g${SHORT_HASH}"
    echo "Generated version (always with hash): ${VERSION}"

    SANITIZED_VERSION=$(echo "$VERSION" | sed 's/[.+-]/_/g')
else
    echo "Not a git repository. Using fallback version: ${VERSION}"
fi

# Print final values to console for local execution and easy debugging
echo "--- Final Version Information ---"
echo "Version: ${VERSION}"
echo "Sanitized Version: ${SANITIZED_VERSION}"
echo "Short Hash: ${SHORT_HASH}"
echo "Long Hash: ${LONG_HASH}"
echo "Commit Timestamp: ${COMMIT_TIMESTAMP}"
echo "Base Version: ${BASE_VERSION}"
echo "Sanitized Base Version: ${SANITIZED_BASE_VERSION}"


# --- Environment-Specific Output ---

if [ -n "$GITHUB_ENV" ] && [ -n "$GITHUB_OUTPUT" ]; then
    echo "--- GitHub Actions environment detected. Setting outputs and env vars. ---"
    
    echo "SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}" >> "$GITHUB_ENV"
    echo "HATCH_VCS_PRETEND_VERSION=${VERSION}" >> "$GITHUB_ENV"
    
    echo "VERSION=${VERSION}" >> "$GITHUB_OUTPUT"
    echo "SANITIZED_VERSION=${SANITIZED_VERSION}" >> "$GITHUB_OUTPUT"
    echo "SHORT_HASH=${SHORT_HASH}" >> "$GITHUB_OUTPUT"
    echo "LONG_HASH=${LONG_HASH}" >> "$GITHUB_OUTPUT"
    echo "COMMIT_TIMESTAMP=${COMMIT_TIMESTAMP}" >> "$GITHUB_OUTPUT" # Now a Unix timestamp
    echo "BASE_VERSION=${BASE_VERSION}" >> "$GITHUB_OUTPUT"
    echo "SANITIZED_BASE_VERSION=${SANITIZED_BASE_VERSION}" >> "$GITHUB_OUTPUT"
else
    export SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}
    export HATCH_VCS_PRETEND_VERSION=${VERSION}
    echo "✅ Local environment variables exported. To use them, run this script with 'source'."
fi