#!/bin/bash

# commit_version.sh - Generates version info for GitHub Actions

# Default to 0.0.0 if not a git repo
VERSION="0.0.0"
SANITIZED_VERSION="0_0_0"
SHORT_HASH="0000000"
LONG_HASH=$(printf '%0.s0' {1..40}) # 40 zeroes as a fallback

# First, check if we are in a git repository.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    # We are in a git repo. Get hashes.
    SHORT_HASH=$(git rev-parse --short HEAD)
    LONG_HASH=$(git rev-parse HEAD)

    # Find the latest tag name (any type)
    LATEST_TAG=$(git describe --tags --abbrev=0 $(git rev-list --tags --max-count=1 2>/dev/null) 2>/dev/null)

    if [[ -z "$LATEST_TAG" ]]; then
        BASE_VERSION="0.0.0" # Use 0.0.0 as the base if no tags exist
    else
        BASE_VERSION=$(echo "$LATEST_TAG" | sed 's/^v//') # Strip the 'v'
    fi
    
    # Create the PEP 440 compliant version (TAG+gHASH)
    VERSION="${BASE_VERSION}+g${SHORT_HASH}"
    # Create a sanitized version for filenames (replace '.' and '+' with '_')
    SANITIZED_VERSION=$(echo "$VERSION" | sed 's/[.+]/-/g')
fi

# Output for GitHub Actions
echo "VERSION=${VERSION}" >> "$GITHUB_OUTPUT"
echo "SANITIZED_VERSION=${SANITIZED_VERSION}" >> "$GITHUB_OUTPUT"
echo "SHORT_HASH=${SHORT_HASH}" >> "$GITHUB_OUTPUT"
echo "LONG_HASH=${LONG_HASH}" >> "$GITHUB_OUTPUT"

# Also print to console for easy debugging
echo "Version: ${VERSION}"
echo "Sanitized Version: ${SANITIZED_VERSION}"
echo "Short Hash: ${SHORT_HASH}"