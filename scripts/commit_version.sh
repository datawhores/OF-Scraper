#!/bin/bash
# A simplified script to generate version information for the build process.

# Exit immediately if any command fails.
set -e

echo "--- Generating Version Info ---"

# --- Get Git Information ---
SHORT_HASH=$(git rev-parse --short HEAD)
LONG_HASH=$(git rev-parse HEAD)
COMMIT_TIMESTAMP=$(git show -s --format=%ct HEAD)

# --- Calculate Version ---
# Get the most recent tag by commit date. Use 0.0.0 as a fallback.
HIGHEST_TAG=$(git tag --sort=-committerdate | head -n 1)
if [ -z "$HIGHEST_TAG" ]; then
    BASE_VERSION="0.0.0"
else
    BASE_VERSION=${HIGHEST_TAG#v} # Remove leading 'v' if it exists
fi

# Construct the final version string, e.g., "3.13.5+g20d752f"
VERSION="${BASE_VERSION}+g${SHORT_HASH}"

# Create a sanitized version for file names, e.g., "3_13_5_g20d752f"
SANITIZED_VERSION=$(echo "$VERSION" | sed 's/[.+-]/_/g')

# --- Print for debugging ---
echo "Base Version: ${BASE_VERSION}"
echo "Commit Hash: ${SHORT_HASH}"
echo "Final Version: ${VERSION}"

# --- Set Outputs for GitHub Actions ---
# These outputs will be available to other jobs in the workflow.
echo "VERSION=${VERSION}" >> $GITHUB_OUTPUT
echo "SANITIZED_VERSION=${SANITIZED_VERSION}" >> $GITHUB_OUTPUT
echo "SHORT_HASH=${SHORT_HASH}" >> $GITHUB_OUTPUT
echo "LONG_HASH=${LONG_HASH}" >> $GITHUB_OUTPUT
echo "COMMIT_TIMESTAMP=${COMMIT_TIMESTAMP}" >> $GITHUB_OUTPUT
echo "BASE_VERSION=${BASE_VERSION}" >> $GITHUB_OUTPUT

echo "--- Version Info Generation Complete ---"
