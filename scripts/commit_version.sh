#!/bin/bash

# commit_version.sh - Generates a PEP 440 compliant version using the highest version tag.

# --- Default fallbacks in case git operations fail ---
VERSION="0.0.0"
SANITIZED_VERSION="0_0_0"
# A nonsensical but valid hash for the fallback case
SHORT_HASH="0000000"
LONG_HASH=$(printf '%0.s0' {1..40}) # 40 zeroes

# --- Check if we are in a git repository ---
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    # We are in a git repo. Get the current commit hash.
    SHORT_HASH=$(git rev-parse --short HEAD)
    LONG_HASH=$(git rev-parse HEAD)

    # --- Find the highest version tag using your proposed logic ---
    # 1. List all tags
    # 2. Filter for tags that look like a version number (e.g., v1.2.3, 2.0, 3.1.beta1)
    # 3. Sort them using a natural version sort (so 1.10.0 > 1.2.0), in reverse order
    # 4. Take the first one from the list, which is the highest version
    HIGHEST_TAG=$(git tag --list | \
                  grep -E '^v?[0-9]+\.[0-9]+(\.[0-9]+)?(\.[a-zA-Z0-9]+)?$' | \
                  sort -V -r | \
                  head -n 1)

    # --- Determine the base version ---
    if [[ -z "$HIGHEST_TAG" ]]; then
        # No tags matching the pattern were found. Use '0.0.0' as the base.
        BASE_VERSION="0.0.0"
        echo "No valid version tags found. Using fallback base version: ${BASE_VERSION}"
    else
        # A tag was found. Strip the leading 'v' if it exists.
        BASE_VERSION=$(echo "$HIGHEST_TAG" | sed 's/^v//')
        echo "Highest version tag found: ${BASE_VERSION}"
    fi
    
    # --- Create the PEP 440 compliant version string (TAG+gHASH) ---
    VERSION="${BASE_VERSION}+g${SHORT_HASH}"
    SANITIZED_VERSION=$(echo "$VERSION" | sed 's/[.+]/_/g')
else
    # Not a git repository. The default fallback values will be used.
    echo "Not a git repository. Using fallback version: ${VERSION}"
fi

# --- Output for GitHub Actions ---
echo "VERSION=${VERSION}" >> "$GITHUB_OUTPUT"
echo "SANITIZED_VERSION=${SANITIZED_VERSION}" >> "$GITHUB_OUTPUT"
echo "SHORT_HASH=${SHORT_HASH}" >> "$GITHUB_OUTPUT"
echo "LONG_HASH=${LONG_HASH}" >> "$GITHUB_OUTPUT"

# Also print to console for easy debugging
echo "Version: ${VERSION}"
echo "Sanitized Version: ${SANITIZED_VERSION}"
echo "Short Hash: ${SHORT_HASH}"