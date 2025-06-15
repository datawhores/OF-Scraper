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
SHOULD_APPLY_STABLE_LATEST="false" # Default to false
SHOULD_APPLY_DEV_LATEST="false"   # Default to false
CURRENT_COMMIT_TIMESTAMP="" # Initialize; will be populated only if registry inspection runs

# Determine if running in GitHub Actions CI
IS_GITHUB_ACTIONS="false"
if [ -n "$GITHUB_ACTIONS" ]; then
    IS_GITHUB_ACTIONS="true"
fi

# --- Determine version and Git info ---
if [ "$IS_GITHUB_ACTIONS" = "true" ]; then
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


# --- Determine if it's a stable or dev release based on PACKAGE_VERSION ---
# Stable: pure semantic versioning (e.g., 1.2.3)
# Dev: contains any letters (e.g., alpha, beta, rc, dev)
if [[ "$PACKAGE_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    IS_STABLE_RELEASE="true"
elif [[ "$PACKAGE_VERSION" =~ [a-zA-Z] ]]; then
    IS_DEV_RELEASE="true"
fi

# --- Determine if Latest/Dev Tags Should Be Applied ---
# This logic requires `skopeo` and `jq` to be installed on the runner.
# Only attempt registry inspection if running in GitHub Actions AND skopeo is available (due to workflow conditional install).
if [ "$IS_GITHUB_ACTIONS" = "true" ] && command -v skopeo &> /dev/null; then # Check if skopeo is installed and accessible
    # Get timestamp of the current commit (epoch seconds)
    CURRENT_COMMIT_TIMESTAMP=$(git log -1 --format=%ct)

    # Function to get tag creation timestamp from registry using skopeo
    get_registry_tag_timestamp() {
        local REGISTRY="$1"
        local REPO="$2"
        local TAG="$3"
        local FULL_IMAGE="docker://$REGISTRY/$REPO:$TAG"
        local CREATED_AT_TIMESTAMP=0

        echo "Checking registry tag: $FULL_IMAGE"

        # skopeo inspect --raw gets the manifest, jq extracts Created field
        CREATED_ISO=$(skopeo inspect --raw "$FULL_IMAGE" 2>/dev/null | jq -r '.Created // ""')

        if [ -n "$CREATED_ISO" ] && [ "$CREATED_ISO" != "null" ]; then
            CREATED_AT_TIMESTAMP=$(date -d "$CREATED_ISO" +%s)
            echo "Found tag $FULL_IMAGE created at $CREATED_ISO (Epoch: $CREATED_AT_TIMESTAMP)"
        else
            echo "Tag $FULL_IMAGE not found or creation time not available."
        fi
        echo "$CREATED_AT_TIMESTAMP"
    }

    # --- Get timestamps of existing 'latest' and 'dev' tags from registries ---
    # GITHUB_REPOSITORY_SLUG is passed as an environment variable to the script step in the workflow
    LAST_STABLE_HUB_TIMESTAMP=$(get_registry_tag_timestamp "docker.io" "datawhores/of-scraper" "latest")
    LAST_STABLE_GHCR_TIMESTAMP=$(get_registry_tag_timestamp "ghcr.io" "$(echo "$GITHUB_REPOSITORY_SLUG" | cut -d'/' -f2)" "latest")

    LAST_DEV_HUB_TIMESTAMP=$(get_registry_tag_timestamp "docker.io" "datawhores/of-scraper" "dev")
    LAST_DEV_GHCR_TIMESTAMP=$(get_registry_tag_timestamp "ghcr.io" "$(echo "$GITHUB_REPOSITORY_SLUG" | cut -d'/' -f2)" "dev")

    # --- Determine `should_apply_stable_latest` ---
    if [[ "$IS_STABLE_RELEASE" == "true" ]]; then
        if (( CURRENT_COMMIT_TIMESTAMP > LAST_STABLE_HUB_TIMESTAMP )) || \
           (( CURRENT_COMMIT_TIMESTAMP > LAST_STABLE_GHCR_TIMESTAMP )) || \
           (("$LAST_STABLE_HUB_TIMESTAMP" == "0" && "$LAST_STABLE_GHCR_TIMESTAMP" == "0")); then
            SHOULD_APPLY_STABLE_LATEST="true"
        fi
    fi

    # --- Determine `should_apply_dev_latest` ---
    if [[ "$IS_DEV_RELEASE" == "true" ]]; then
        if (( CURRENT_COMMIT_TIMESTAMP > LAST_DEV_HUB_TIMESTAMP )) || \
           (( CURRENT_COMMIT_TIMESTAMP > LAST_DEV_GHCR_TIMESTAMP )) || \
           (("$LAST_DEV_HUB_TIMESTAMP" == "0" && "$LAST_DEV_GHCR_TIMESTAMP" == "0")); then
            SHOULD_APPLY_DEV_LATEST="true"
        fi
    fi

    # Debug prints for GitHub Actions environment
    echo "Debug - Current commit timestamp: $CURRENT_COMMIT_TIMESTAMP"
    echo "Debug - Latest Stable Hub Timestamp: $LAST_STABLE_HUB_TIMESTAMP"
    echo "Debug - Latest Stable GHCR Timestamp: $LAST_STABLE_GHCR_TIMESTAMP"
    echo "Debug - Latest Dev Hub Timestamp: $LAST_DEV_HUB_TIMESTAMP"
    echo "Debug - Latest Dev GHCR Timestamp: $LAST_DEV_GHCR_TIMESTAMP"
else
    echo "Skipping registry inspection (not in GH Actions or skopeo not installed)."
fi

# --- Print final values to console (for local execution and debugging) ---
echo "Final Package Version: ${PACKAGE_VERSION}"
echo "Long Commit Hash: ${LONG_HASH}"
echo "Short Commit Hash: ${SHORT_HASH}"
echo "Is Stable Release: ${IS_STABLE_RELEASE}"
echo "Is Dev Release: ${IS_DEV_RELEASE}"
echo "Should Apply Stable Latest: ${SHOULD_APPLY_STABLE_LATEST}"
echo "Should Apply Dev Latest: ${SHOULD_APPLY_DEV_LATEST}"
echo "Commit Timestamp (from HEAD): ${CURRENT_COMMIT_TIMESTAMP}"


# --- Environment-Specific Output (for GitHub Actions) ---
if [ "$IS_GITHUB_ACTIONS" = "true" ] && [ -n "$GITHUB_ENV" ] && [ -n "$GITHUB_OUTPUT" ]; then
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
    
    # Only output should_apply_* and commit_timestamp if they were actually calculated by registry inspection
    if [ "$SHOULD_APPLY_STABLE_LATEST" != "false" ] || [ "$SHOULD_APPLY_STABLE_LATEST" != "true" ]; then # Check if default value changed
        echo "should_apply_stable_latest=${SHOULD_APPLY_STABLE_LATEST}" >> "$GITHUB_OUTPUT"
    fi
    if [ "$SHOULD_APPLY_DEV_LATEST" != "false" ] || [ "$SHOULD_APPLY_DEV_LATEST" != "true" ]; then # Check if default value changed
        echo "should_apply_dev_latest=${SHOULD_APPLY_DEV_LATEST}" >> "$GITHUB_OUTPUT"
    fi
    if [ -n "$CURRENT_COMMIT_TIMESTAMP" ]; then
        echo "commit_timestamp=${CURRENT_COMMIT_TIMESTAMP}" >> "$GITHUB_OUTPUT"
    fi
else
    # Local Use: Export variables. This only works if the script is run with `source`.
    export SETUPTOOLS_SCM_PRETEND_VERSION=${PACKAGE_VERSION}
    export HATCH_VCS_PRETEND_VERSION=${PACKAGE_VERSION}
    echo "✅ Local environment variables exported. To use them, run this script with 'source'."
fi