#!/bin/bash

# set build env, run with source

# Step 1: Get the version from git directly into a variable.
# If the git command fails, the '||' will execute the echo command,
# providing "0.0.0" as a fallback value for the variable.
VERSION=$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || echo "0.0.0")
echo "Version resolved to: ${VERSION}"

# Step 2: Export the version to the required environment variables
export HATCH_VCS_PRETEND_VERSION=$VERSION
export SETUPTOOLS_SCM_PRETEND_VERSION=$VERSION

echo "Build environment variables exported:"
echo "HATCH_VCS_PRETEND_VERSION=${HATCH_VCS_PRETEND_VERSION}"
echo "SETUPTOOLS_SCM_PRETEND_VERSION=${SETUPTOOLS_SCM_PRETEND_VERSION}"