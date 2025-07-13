# plugins.py
# This script dynamically generates a version using git, but prioritizes
# an environment variable if it is available, ensuring CI/CD compatibility.

import re
import subprocess
import os

def get_version_dict():
    """
    Attempts to get the version, prioritizing the HATCH_VCS_PRETEND_VERSION
    environment variable, then falling back to git history.
    """
    
    # --- Step 1: Check for Environment Variable Override ---
    # This is the highest priority. If this variable is set (e.g., by your
    # GitHub Actions workflow), we use it directly and stop.
    if "HATCH_VCS_PRETEND_VERSION" in os.environ:
        version = os.environ["HATCH_VCS_PRETEND_VERSION"]
        print(f"--> [version-pioneer] Found environment variable. Using version: {version}")
        return {'version': version}

    # --- Step 2: Fallback to Git Logic if no environment variable is found ---
    try:
        # Check if we are in a git repository before proceeding.
        subprocess.check_output(['git', 'rev-parse', '--is-inside-work-tree'], stderr=subprocess.DEVNULL)
        print("--> [version-pioneer] No environment variable found. Determining version from Git...")

        # Find the highest version tag based on the newest commit date.
        git_tag_cmd = ['git', 'tag', '--sort=-committerdate']
        tags = subprocess.check_output(git_tag_cmd, text=True, stderr=subprocess.DEVNULL).strip().split('\n')

        base_version = "0.0.0"
        version_regex = re.compile(r'^v?([0-9]+\.[0-9]+(\.[0-9]+)?([-.][a-zA-Z0-9.]+)?)$')
        
        for tag in tags:
            if tag and version_regex.match(tag):
                base_version = tag.lstrip('v')
                print(f"--> Found base version from newest valid tag: {base_version}")
                break
        else:
            print("--> No valid version tags found. Using fallback '0.0.0'.")

        # Get the short commit hash for the current commit.
        short_hash_cmd = ['git', 'rev-parse', '--short', 'HEAD']
        short_hash = subprocess.check_output(short_hash_cmd, text=True, stderr=subprocess.DEVNULL).strip()

        # Generate the final version string.
        version = f"{base_version}+g{short_hash}"

    except (subprocess.CalledProcessError, FileNotFoundError):
        # This block will execute if git isn't found or a command fails.
        print("--> git command failed. Falling back to static version.")
        version = "0.0.0+unknown"

    print(f"--> Final version determined: {version}")
    
    # Return the version in the dictionary format required by hatchling.
    return {'version': version}
