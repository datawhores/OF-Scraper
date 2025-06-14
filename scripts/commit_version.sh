#!/bin/bash

# A best practice for scripts: exit immediately if any command fails.
set -e

# --- Default fallbacks ---
VERSION="0.0.0+g0000000"
SANITIZED_VERSION="0_0_0_g0000000"
SHORT_HASH="0000000"
LONG_HASH=$(printf '%0.s0' {1..40})
COMMIT_TIMESTAMP="000000000000"
BASE_VERSION="0.0.0" # Ensure BASE_VERSION is always defined

# --- Check if we are in a git repository ---
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    # We are in a git repo. Get the current commit hashes.
    SHORT_HASH=$(git rev-parse --short HEAD)
    LONG_HASH=$(git rev-parse HEAD)

    # Get the committer date of HEAD for chronological release sorting
    COMMIT_TIMESTAMP=$(git show -s --format=%ci HEAD | awk '{print $1" "$2}' | sed 's/[-:]//g' | cut -c 1-12)
    echo "Commit Timestamp: ${COMMIT_TIMESTAMP}"

    # Find the highest version tag (Sorted by Committer Date for base)
    HIGHEST_TAG=$(git tag --sort=-committerdate | \
                  grep -E '^v?[0-9]+\.[0-9]+(\.[0-9]+)?([-.][a-zA-Z0-9.]+)?$' | \
                  head -n 1)

    # Determine the base version
    if [ -z "$HIGHEST_TAG" ]; then
        BASE_VERSION="0.0.0"
        echo "No valid version tags found pointing to recent commits. Using fallback base version: ${BASE_VERSION}"
    else
        # Remove 'v' prefix if present
        BASE_VERSION=$(echo "$HIGHEST_TAG" | sed 's/^v//')
        echo "Base version from newest commit tag: ${BASE_VERSION}"
    fi
    
    # Always add the short hash for the final version
    VERSION="${BASE_VERSION}+g${SHORT_HASH}"
    echo "Generated version (always with hash): ${VERSION}"

    # Sanitize the version for file names. Replace dots, hyphens, and pluses with underscores.
    SANITIZED_VERSION=$(echo "$VERSION" | sed 's/[.+-]/_/g')
else
    # Not a git repository. The default fallback values will be used.
    echo "Not a git repository. Using fallback version: ${VERSION}"
fi

# Print final values to console for local execution and easy debugging
echo "--- Final Version Information ---"
echo "Version: ${VERSION}"
echo "Sanitized Version: ${SANITIZED_VERSION}"
echo "Short Hash: ${SHORT_HASH}"
echo "Long Hash: ${LONG_HASH}"
echo "Commit Timestamp: ${COMMIT_TIMESTAMP}"
echo "Base Version: ${BASE_VERSION}" # Echo base version for local debugging


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
    echo "SHORT_HASH=${SHORT_HASH}" >> "$GITHUB_OUTPUT"
    echo "LONG_HASH=${LONG_HASH}" >> "$GITHUB_OUTPUT"
    echo "COMMIT_TIMESTAMP=${COMMIT_TIMESTAMP}" >> "$GITHUB_OUTPUT"
    echo "BASE_VERSION=${BASE_VERSION}" >> "$GITHUB_OUTPUT" # <-- ADD THIS LINE
else
    # Local Use: Export variables. This only works if the script is run with `source`.
    export SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}
    export HATCH_VCS_PRETEND_VERSION=${VERSION}
    echo "✅ Local environment variables exported. To use them, run this script with 'source'."
fi