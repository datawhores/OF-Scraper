#!/bin/bash
set -euo pipefail

# --- Configuration Variables ---
APP_USER="${USERNAME:-ofscraper}"
APP_GROUP="${GROUPNAME:-$APP_USER}"
#home
APP_HOME_FOLDER="${HOME_FOLDER:-$APP_USER}"
APP_HOME="/home/$APP_HOME_FOLDER"

# ----------------s ---
CURRENT_UID="$(id -u)"
# Global flags to indicate if user/group could be set up for gosu
_group_setup_for_gosu=false
_user_setup_for_gosu=false

# Global APP_UID and APP_GID (will be set by determine_app_ids)
APP_UID=""
APP_GID=""

# --- Source Libraries ---
# Ensure these paths are correct relative to where entrypoint.sh runs
. /usr/local/bin/lib_user_setup.sh      # Contains determine_app_ids, setup_group, setup_user
. /usr/local/bin/lib_permissions.sh    # Contains handle_permissions
. /usr/local/bin/lib_python_deps.sh    # Contains install_python_deps_conditionally
. /usr/local/bin/lib_paths.sh          # Contains functions to modify mount paths

# You might want to place these lib files in a directory like /usr/local/bin
# within your Docker image.

# Main execution logic
main() {
    if [ "$CURRENT_UID" -eq 0 ]; then
        determine_app_ids
        setup_group
        setup_user
        handle_permissions
        install_python_deps_conditionally

        if $_user_setup_for_gosu; then
            echo "INFO: Dropping privileges to user '$APP_USER' (UID: $APP_UID) and executing command: $*"
            exec gosu "$APP_USER" "$@"
        else
            echo "CRITICAL: User '$APP_USER' could not be properly set up for gosu. Running command as current user (root/remapped root)."
            echo "WARNING: This may lead to permission issues if the application expects to run as '$APP_USER' and cannot write to its data or config directories."
            exec "$@" # Execute command as current user (root/remapped root)
        fi
    else
        # Running as non-root: Use existing user
        set_up_mount_paths
        echo "INFO: Running as non-root (UID: $CURRENT_UID). Executing command as current user: $*"
        # Ensure the target home, data, and config directories edaxist, but don't change ownership if not root
        mkdir -p "$APP_HOME" "$DATA_DIR" "$CONFIG_DIR"
        exec "$@"
    fi
}

# Call the main function to start execution
main "$@"