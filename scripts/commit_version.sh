#!/bin/bash

# A best practice for scripts: exit immediately if any command fails.
set -e

# --- Default fallbacks for all outputs ---
VERSION="0.0.0+g0000000"
SANITIZED_VERSION="0_0_0_g0000000"
SHORT_HASH="0000000"
LONG_HASH=$(printf '%0.s0' {1..40})
COMMIT_TIMESTAMP="0000000000" # Unix timestamp (e.g., 1678886730)
BASE_VERSION="0.0.0"
SANITIZED_BASE_VERSION="0-0-0"
PUSH_TYPE="unknown" # Will be "initial_push", "fast_forward_or_merge", "rewind_or_older_commit_pushed", "non_linear_force_push"
IS_NEWER="false" # Boolean string "true" or "false"

# --- Check if we are in a git repository ---
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    # Get current commit hashes
    SHORT_HASH=$(git rev-parse --short HEAD)
    LONG_HASH=$(git rev-parse HEAD)

    # Get the committer date of HEAD as a Unix timestamp for chronological sorting
    COMMIT_TIMESTAMP=$(git show -s --format=%ct HEAD)
    echo "Commit Timestamp (Unix): ${COMMIT_TIMESTAMP}"

    # Find the highest version tag based on newest commit date (committerdate)
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
    
    # Sanitize BASE_VERSION for use in Git tag/Docker tag names (replace . and + with -)
    SANITIZED_BASE_VERSION=$(echo "$BASE_VERSION" | sed 's/[.+]/_/g')
    echo "Sanitized Base Version: ${SANITIZED_BASE_VERSION}"

    # Generate the full version string (always with hash for development builds)
    VERSION="${BASE_VERSION}+g${SHORT_HASH}"
    echo "Generated version (always with hash): ${VERSION}"

    # Sanitize the full version string for file/directory names (replace . + - with _)
    SANITIZED_VERSION=$(echo "$VERSION" | sed 's/[.+-]/_/g')

    # --- Determine Push Direction (Requires GITHUB_EVENT_BEFORE) ---
    # GITHUB_EVENT_BEFORE is passed from workflow as an environment variable
    BEFORE_SHA="${GITHUB_EVENT_BEFORE:-0000000000000000000000000000000000000000}"
    
    if [ "$BEFORE_SHA" = "0000000000000000000000000000000000000000" ]; then
      PUSH_TYPE="initial_push"
      echo "Push is an initial push to the branch."
    elif git merge-base --is-ancestor "$LONG_HASH" "$BEFORE_SHA" >/dev/null 2>&1; then
      PUSH_TYPE="rewind_or_older_commit_pushed"
      echo "Push direction: Branch moved backward or an older commit was pushed."
    elif git merge-base --is-ancestor "$BEFORE_SHA" "$LONG_HASH" >/dev/null 2>&1; then
      PUSH_TYPE="fast_forward_or_merge"
      echo "Push direction: Standard fast-forward or merge."
    else
      PUSH_TYPE="non_linear_force_push"
      echo "Push direction: Non-linear force push (e.g., rebase or unrelated history merge)."
    fi
    echo "Push Type: ${PUSH_TYPE}"

    # --- Calculate is_newer_than_last_successful_run ---
    if [ -n "$GH_TOKEN" ] && [ -n "$GITHUB_REPOSITORY" ] && [ -n "$GITHUB_REF" ] && [ -n "$GITHUB_WORKFLOW_REF" ]; then
      # --- FINAL WORKFLOW_ID FIX: Dynamically derive workflow file name from GITHUB_WORKFLOW_REF ---
      # This is the most robust and dynamic way to get the workflow ID for the gh api call
      WORKFLOW_PATH_FROM_ROOT="${GITHUB_WORKFLOW_REF#*/.github/workflows/}" # Remove leading path part
      WORKFLOW_ID="${WORKFLOW_PATH_FROM_ROOT%@*}" # Remove "@ref" part
      echo "DEBUG: Final WORKFLOW_ID for API call: '${WORKFLOW_ID}' (Dynamically derived from GITHUB_WORKFLOW_REF)"
      # (The previous debug echoes for raw ref and parsing steps are removed for conciseness)

      echo "DEBUG: Attempting to query workflow runs for workflow ID '$WORKFLOW_ID' on branch '$GITHUB_REF'."
      # This is the confirmed working gh api call with query parameters in the URL string
      LAST_SUCCESSFUL_RUN_SHA=$(gh api \
        --paginate \
        "/repos/${GITHUB_REPOSITORY}/actions/workflows/${WORKFLOW_ID}/runs?status=success&event=push" \
        --jq '.workflow_runs[0].head_sha' \
        --header 'Accept: application/vnd.github.com/v3+okay I have a smilar script called release_version.sh



I want to incorpate is usage into this script



I want this script to also handle maybe updating latest if it is newer than the last json' \
        --header 'X-GitHub-Api-Version: 2022-11-28' \
        2>/dev/null | head -n 1) # Suppress stderr, take first line

      echo "Last successful run SHA: ${LAST_SUCCESSFUL_RUN_SHA:-None}"

      if [ -z "$LAST_SUCCESSFUL_RUN_SHA" ]; then
        IS_NEWER="true"
      elif [ "$LONG_HASH" = "$LAST_SUCCESSFUL_RUN_SHA" ]; then
        IS_NEWER="false"
      elif git merge-base --is-ancestor "$LAST_SUCCESSFUL_RUN_SHA" "$LONG_HASH" >/dev/null 2>&1; then
        IS_NEWER="true"
      else
        IS_NEWER="false"
      fi
    else
      echo "Insufficient GitHub Actions environment variables (GH_TOKEN, GITHUB_REPOSITORY, GITHUB_REF, or GITHUB_WORKFLOW_REF missing) to calculate 'is_newer_than_last_successful_run'."
      IS_NEWER="false"
    fi
    echo "Is Newer Than Last Successful Run: ${IS_NEWER}"

else # Not a git repository
    echo "Not a git repository. Using fallback versions and status."
fi

# Print final values for local debugging
echo "--- Final Version Information ---"
echo "Version: ${VERSION}"
echo "Sanitized Version: ${SANITIZED_VERSION}"
echo "Short Hash: ${SHORT_HASH}"
echo "Long Hash: ${LONG_HASH}"
echo "Commit Timestamp: ${COMMIT_TIMESTAMP}"
echo "Base Version: ${BASE_VERSION}"
echo "Sanitized Base Version: ${SANITIZED_BASE_VERSION}"
echo "Push Type: ${PUSH_TYPE}"
echo "Is Newer Than Last Successful Run: ${IS_NEWER}"


# --- Environment-Specific Output ---
if [ -n "$GITHUB_ENV" ] && [ -n "$GITHUB_OUTPUT" ]; then
    echo "--- GitHub Actions environment detected. Setting outputs and env vars. ---"
    
    echo "SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}" >> "$GITHUB_ENV"
    echo "HATCH_VCS_PRETEND_VERSION=${VERSION}" >> "$GITHUB_ENV"
    
    echo "VERSION=${VERSION}" >> "$GITHUB_OUTPUT"
    echo "SANITIZED_VERSION=${SANITIZED_VERSION}" >> "$GITHUB_OUTPUT"
    echo "SHORT_HASH=${SHORT_HASH}" >> "$GITHUB_OUTPUT"
    echo "LONG_HASH=${LONG_HASH}" >> "$GITHUB_OUTPUT"
    echo "COMMIT_TIMESTAMP=${COMMIT_TIMESTAMP}" >> "$GITHUB_OUTPUT"
    echo "BASE_VERSION=${BASE_VERSION}" >> "$GITHUB_OUTPUT"
    echo "SANITIZED_BASE_VERSION=${SANITIZED_BASE_VERSION}" >> "$GITHUB_OUTPUT"
    echo "PUSH_TYPE=${PUSH_TYPE}" >> "$GITHUB_OUTPUT"
    echo "IS_NEWER_THAN_LAST_SUCCESSFUL_RUN=${IS_NEWER}" >> "$GITHUB_OUTPUT"
else
    export SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}
    export HATCH_VCS_PRETEND_VERSION=${VERSION}
    echo "✅ Local environment variables exported. To use them, run this script with 'source'."
fi