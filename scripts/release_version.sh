#!/bin/bash

# set build env, run with source

# Step 1: Get the latest tag (any type) and include commit count and hash.
# We do this by REMOVING --abbrev=0.
RAW_VERSION=$(git describe --tags $(git rev-list --tags --max-count=1 2>/dev/null) 2>/dev/null)

# Step 2: Check if we actually got a version. If not, use the fallback.
if [[ -z "$RAW_VERSION" ]]; then
  # This will only happen if there are NO tags of any kind.
  VERSION="0.0.0"
  echo "No tags found. Using fallback version: ${VERSION}"
else
  # A version string was found, so strip the leading 'v' if it exists.
  VERSION=$(echo "$RAW_VERSION" | sed 's/^v//')
  echo "Version resolved from git describe: ${VERSION}"
fi

# Step 3: Export the final version.
export HATCH_VCS_PRETEND_VERSION=$VERSION
export SETUPTOOLS_SCM_PRETEND_VERSION=$VERSION

echo "Build environment variables exported:"
echo "HATCH_VCS_PRETEND_VERSION=${HATCH_VCS_PRETEND_VERSION}"
echo "SETUPTOOLS_SCM_PRETEND_VERSION=${SETUPTOOLS_SCM_PRETEND_VERSION}"