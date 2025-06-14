#!/bin/bash

# A best practice for scripts: exit immediately if any command fails.
set -e

# --- Default fallbacks ---
VERSION="0.0.0+g0000000" # Updated default to always include hash format
SANITIZED_VERSION="0_0_0_g0000000" # Updated default
SHORT_HASH="0000000"
LONG_HASH=$(printf '%0.s0' {1..40})

# --- Check if we are in a git repository ---
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    # We are in a git repo. Get the current commit hashes.
    SHORT_HASH=$(git rev-parse --short HEAD)
    LONG_HASH=$(git rev-parse HEAD)

    # --- Find the highest version tag (Sorted by Committer Date) ---
    # Find the tag pointing to the most recently committed code.
    # We sort by committerdate in reverse (-committerdate) to put the newest commit first,
    # then filter for version-like tags, and take the very first match.
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
    
    # --- ALWAYS add the short hash for the final version ---
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


# --- Environment-Specific Output ---

# Check if we are in a GitHub Action
if [ -n "$GITHUB_ENV" ] && [ -n "$GITHUB_OUTPUT" ]; then
    # GitHub Actions: Write to special files
    echo "--- GitHub Actions environment detected. Setting outputs and env vars. ---"
    
    # For subsequent steps in the same job
    echo "SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}" >> "$GITHUB_ENV"
    echo "HATCH_VCS_PRETEND_VERSION=${VERSION}" >> "$GITHUB_ENV"
    
    # For other jobs that depend on this one
    echo "VERSION=${VERSION}" >> "$GITHUB_OUTPUT"
    echo "SANITIZED_VERSION=${SANITIZED_VERSION}" >> "$GITHUB_OUTPUT"
    echo "SHORT_HASH=${SHORT_HASH}" >> "$GITHUB_OUTPUT"
    echo "LONG_HASH=${LONG_HASH}" >> "$GITHUB_OUTPUT"
else
    # Local Use: Export variables to the current shell.
    # This only works if the script is run with `source`.
    export SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}
    export HATCH_VCS_PRETEND_VERSION=${VERSION}
    echo "✅ Local environment variables exported. Run 'source ./scripts/commit_version.sh' for them to persist."
fi