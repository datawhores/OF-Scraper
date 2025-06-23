#!/bin/bash
set -e

# --- Get input version from environment variable ---
# In GitHub Actions, INPUT_VERSION is passed from the workflow dispatch.
# Locally, if not set, it defaults to empty, triggering fallback to Git tags.
INPUT_VERSION="${INPUT_VERSION:-}"

# --- Initialize outputs ---
PACKAGE_VERSION=""
LONG_HASH=""
SHORT_HASH=""
IS_STABLE_RELEASE="false"
IS_DEV_RELEASE="false"
CURRENT_COMMIT_TIMESTAMP="" # Will be populated from git log
# GITHUB_ACTIONS is already set to 'true' in the CI environment, no need to redefine IS_GITHUB_ACTIONS

# --- Determine version and Git info ---
# Directly use $GITHUB_ACTIONS for the check
if [ "$GITHUB_ACTIONS" = "true" ]; then
    # Scenario: Running in GitHub Actions. INPUT_VERSION is REQUIRED by workflow_dispatch.
    if [ -z "$INPUT_VERSION" ]; then
        echo "Error: INPUT_VERSION is required when running in GitHub Actions, but it is empty." >&2
        exit 1 # Fail fast if a required input is missing in CI
    fi
    PACKAGE_VERSION=$(echo "$INPUT_VERSION" | sed 's/^v//')
    
    # Get the commit hash for the input tag/version
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        # Check if INPUT_VERSION is a valid Git ref (tag or branch)
        if git show-ref --quiet --tags "${INPUT_VERSION}" || git show-ref --quiet --heads "${INPUT_VERSION}"; then
            LONG_HASH=$(git rev-parse "${INPUT_VERSION}")
        else
            # Fallback if INPUT_VERSION is just a string not a ref, use current HEAD
            LONG_HASH=$(git rev-parse HEAD)
        fi
    else
        echo "Warning: Not in a git repository. Cannot determine commit hash for INPUT_VERSION." >&2
        LONG_HASH="unknown" # Fallback if not in git repo during CI (unlikely with checkout action)
    fi
    echo "Using INPUT_VERSION: ${INPUT_VERSION} (Running in GitHub Actions)"
else
    # Scenario: Not running in GitHub Actions (local execution). Handle INPUT_VERSION or fallback.
    if [ -n "$INPUT_VERSION" ]; then
        PACKAGE_VERSION=$(echo "$INPUT_VERSION" | sed 's/^v//')
        if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
             if git show-ref --quiet --tags "${INPUT_VERSION}" || git show-ref --quiet --heads "${INPUT_VERSION}"; then
                LONG_HASH=$(git rev-parse "${INPUT_VERSION}")
            else
                LONG_HASH=$(git rev-parse HEAD)
            fi
        fi
        echo "Using INPUT_VERSION: ${INPUT_VERSION} (Local execution)"
    else
        # INPUT_VERSION NOT provided locally, fall back to Git tags
        if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
            LONG_HASH=$(git rev-parse HEAD)
            HIGHEST_TAG=$(git tag --sort=-committerdate | \
                          grep -E '^v?[0-9]+\.[0-9]+(\.[0-9]+)?([-.][a-zA-Z0-9.]+)?$' | \
                          head -n 1)

            if [ -n "$HIGHEST_TAG" ]; then
                PACKAGE_VERSION=$(echo "$HIGHEST_TAG" | sed 's/^v//')
                echo "INPUT_VERSION not set. Derived version from Git tag: ${PACKAGE_VERSION} (Local execution)"
            else
                PACKAGE_VERSION="0.0.0"
                echo "INPUT_VERSION not set and no valid Git tags found. Using fallback version: ${PACKAGE_VERSION} (Local execution)"
            fi
        else
            PACKAGE_VERSION="0.0.0"
            echo "Not a git repository. Using fallback version: ${PACKAGE_VERSION} (Local execution)"
        fi
    fi
fi

# Derive short hash AFTER LONG_HASH is determined
if [ -n "$LONG_HASH" ] && [ "$LONG_HASH" != "unknown" ]; then
    SHORT_HASH=$(echo "${LONG_HASH}" | cut -c1-7)
else
    SHORT_HASH="unknown"
fi

# Get timestamp of the current commit (epoch seconds)
if [ -n "$LONG_HASH" ] && [ "$LONG_HASH" != "unknown" ]; then
    # Ensure the exact commit is checked out for consistent timestamp
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        CURRENT_COMMIT_TIMESTAMP=$(git log -1 --format=%ct "${LONG_HASH}")
    else
        echo "Warning: Not in a git repository. Cannot determine commit timestamp for HEAD." >&2
        CURRENT_COMMIT_TIMESTAMP="0"
    fi
else
    CURRENT_COMMIT_TIMESTAMP="0"
fi

# --- Determine if it's a stable or dev release based on PACKAGE_VERSION ---
# Stable: pure semantic versioning (e.g., 1.2.3)
# Dev: contains any letters (e.g., alpha, beta, rc, dev)
if [[ "$PACKAGE_VERSION" =~ [a-zA-Z] ]]; then
    IS_DEV_RELEASE="true"
else
    IS_STABLE_RELEASE="true"
fi

# Debug prints for console (for local execution and debugging)
echo "Final Package Version: ${PACKAGE_VERSION}"
echo "Long Commit Hash: ${LONG_HASH}"
echo "Short Commit Hash: ${SHORT_HASH}"
echo "Is Stable Release: ${IS_STABLE_RELEASE}"
echo "Is Dev Release: ${IS_DEV_RELEASE}"
echo "Current Commit Timestamp (from HEAD): ${CURRENT_COMMIT_TIMESTAMP}"


# --- Environment-Specific Output (for GitHub Actions) ---
# Directly use $GITHUB_ACTIONS for the check
if [ "$GITHUB_ACTIONS" = "true" ] && [ -n "$GITHUB_ENV" ] && [ -n "$GITHUB_OUTPUT" ]; then
    echo "--- GitHub Actions environment detected. Setting outputs and env vars. ---"

    # For subsequent steps in the same job (e.g., for build arguments)
    echo "SETUPTOOLS_SCM_PRETEND_VERSION=${PACKAGE_VERSION}" >> "$GITHUB_ENV"
    echo "HATCH_VCS_PRETEND_VERSION=${PACKAGE_VERSION}" >> "$GITHUB_ENV"

    # For other jobs that depend on this one
    echo "long_hash=${LONG_HASH}" >> "$GITHUB_OUTPUT"
    echo "short_hash=${SHORT_HASH}" >> "$GITHUB_OUTPUT"
    echo "package_version=${PACKAGE_VERSION}" >> "$GITHUB_OUTPUT"
    echo "is_stable_release=${IS_STABLE_RELEASE}" >> "$GITHUB_OUTPUT"
    echo "is_dev_release=${IS_DEV_RELEASE}" >> "$GITHUB_OUTPUT"
    echo "commit_timestamp=${CURRENT_COMMIT_TIMESTAMP}" >> "$GITHUB_OUTPUT"
else
    # Local Use: Export variables. This only works if the script is run with `source`.
    export SETUPTOOLS_SCM_PRETEND_VERSION=${PACKAGE_VERSION}
    export HATCH_VCS_PRETEND_VERSION=${PACKAGE_VERSION}
    echo "✅ Local environment variables exported. To use them, run this script with 'source'."
fi