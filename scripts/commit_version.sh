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

    # --- Calculate is_newer_than_last_successful_run (Requires GH_TOKEN, GITHUB_REPOSITORY, GITHUB_WORKFLOW_REF, GITHUB_REF) ---
    # These variables are passed from workflow as environment variables
    if [ -n "$GH_TOKEN" ] && [ -n "$GITHUB_REPOSITORY" ] && [ -n "$GITHUB_WORKFLOW_REF" ] && [ -n "$GITHUB_REF" ]; then
      # Extract workflow file name (e.g., "docker-daily-build.yml") from GITHUB_WORKFLOW_REF
      # This is the most robust way to identify the workflow for the gh api call
      WORKFLOW_FILE_NAME=$(basename "${GITHUB_WORKFLOW_REF}") 
      WORKFLOW_ID="${WORKFLOW_FILE_NAME}" # Use the file name as the ID for gh api call

      echo "DEBUG: Attempting to query workflow runs for workflow '$WORKFLOW_ID' on branch '$GITHUB_REF'." # Debug output
      # Suppress gh error output (stderr) by redirecting to /dev/null, so script doesn't abort on "workflow not found"
      LAST_SUCCESSFUL_RUN_SHA=$(gh api \
        --paginate \
        "/repos/${GITHUB_REPOSITORY}/actions/workflows/${WORKFLOW_ID}/runs" \
        --field status=success \
        --field branch="${GITHUB_REF#refs/heads/}" \
        --field event=push \
        --jq '.workflow_runs[0].head_sha' \
        --header 'Accept: application/vnd.github.v3+json' \
        --header 'X-GitHub-Api-Version: 2022-11-28' \
        2>/dev/null | head -n 1) # Take only the first line/result

      echo "Last successful run SHA: ${LAST_SUCCESSFUL_RUN_SHA:-None}" # Show 'None' if variable is empty for clarity

      if [ -z "$LAST_SUCCESSFUL_RUN_SHA" ]; then
        IS_NEWER="true" # No previous successful run, so this is the first one for this branch/workflow
      elif [ "$LONG_HASH" = "$LAST_SUCCESSFUL_RUN_SHA" ]; then
        IS_NEWER="false" # Current commit is the same as the last successful run's commit (e.g., a re-run of the same commit)
      elif git merge-base --is-ancestor "$LAST_SUCCESSFUL_RUN_SHA" "$LONG_HASH" >/dev/null 2>&1; then
        IS_NEWER="true" # Current commit is a direct descendant (came after) the last successful run's commit -> it's genuinely newer
      else
        IS_NEWER="false" # Current commit is NOT a descendant (e.g., an older commit was pushed, history re-written, or unrelated)
      fi
    else
      echo "Insufficient GitHub Actions environment variables to calculate 'is_newer_than_last_successful_run'."
      echo "Required: GH_TOKEN, GITHUB_REPOSITORY, GITHUB_WORKFLOW_REF, GITHUB_REF."
      IS_NEWER="false" # Default to false if we can't perform the check
    fi
    echo "Is Newer Than Last Successful Run: ${IS_NEWER}"

else # Not a git repository (use default fallbacks)
    echo "Not a git repository. Using fallback versions and status."
fi

# --- Print final values to console for local execution and easy debugging ---
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


# --- Environment-Specific Output (for GitHub Actions workflow outputs) ---
if [ -n "$GITHUB_ENV" ] && [ -n "$GITHUB_OUTPUT" ]; then
    echo "--- GitHub Actions environment detected. Setting outputs and env vars. ---"
    
    # Set environment variables for subsequent steps in the same job (e.g., for setuptools_scm)
    echo "SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}" >> "$GITHUB_ENV"
    echo "HATCH_VCS_PRETEND_VERSION=${VERSION}" >> "$GITHUB_ENV"
    
    # Set outputs for other jobs that depend on this one (e.g., build_and_publish, publish_release)
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
    # Local Use: Export variables to the current shell.
    # This only works if the script is run with `source ./scripts/commit_version.sh`.
    export SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}
    export HATCH_VCS_PRETEND_VERSION=${VERSION}
    echo "✅ Local environment variables exported. To use them, run this script with 'source'."
fi