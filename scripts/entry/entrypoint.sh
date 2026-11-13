#!/bin/bash
set -euo pipefail

# --- Configuration Variables ---
# USER_NAME/GROUP_NAME are the names docker-compose.yml documents;
# USERNAME/GROUPNAME are still accepted
APP_USER="${USER_NAME:-${USERNAME:-ofscraper}}"
APP_GROUP="${GROUP_NAME:-${GROUPNAME:-$APP_USER}}"
#home
APP_HOME="${APP_HOME:-/home/ofscraper}"

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
. /usr/local/bin/entry/lib_user_setup.sh      # Contains determine_app_ids, setup_group, setup_user
. /usr/local/bin/entry/lib_permissions.sh    # Contains handle_permissions
. /usr/local/bin/entry/lib_paths.sh          # Contains functions to modify mount paths

# You might want to place these lib files in a directory like /usr/local/bin
# within your Docker image.

# Main execution logic
main() {
    if [ "$CURRENT_UID" -eq 0 ]; then
        determine_app_ids
        setup_group
        setup_user
        set_up_all_paths
        handle_permissions

        if $_user_setup_for_gosu; then
            echo "INFO: Dropping privileges to user '$APP_USER' (UID: $APP_UID) and executing command: $*"
            exec gosu "$APP_USER" "$@"
        else
            echo "CRITICAL: User '$APP_USER' could not be properly set up for gosu. Running command as current user (root/remapped root)."
            echo "WARNING: This may lead to permission issues if the application expects to run as '$APP_USER' and cannot write to its data or config directories."
            exec "$@" # Execute command as current user (root/remapped root)
        fi
  else
    # Started with --user / 'user:' (e.g. rootless setups). Users can't be
    # created or files chowned without root, so run the command as this user.
    echo "INFO: Running as non-root UID $CURRENT_UID; skipping user setup and permission changes."
    if [ -z "${HOME:-}" ] || [ "$HOME" = "/" ] || [ ! -w "$HOME" ]; then
        export HOME="$APP_HOME"
    fi
    if [ ! -w "$HOME" ]; then
        echo "WARN: HOME ($HOME) is not writable by UID $CURRENT_UID. Mount a writable folder there or set APP_HOME to one."
    fi
    # bash takes UID from the environment when it's passed in, so a value
    # other than the real UID means one was requested
    if [ "${UID:-$CURRENT_UID}" != "$CURRENT_UID" ] || [ -n "${GID:-}${USER_ID:-}${GROUP_ID:-}" ]; then
        echo "INFO: Ignoring UID/GID settings: the container was started as UID $CURRENT_UID (--user), which takes precedence."
    fi
    set_up_all_paths
    mkdir -p "$CONFIG_DIR" "$DATA_DIR" 2>/dev/null || echo "WARN: Could not create $CONFIG_DIR or $DATA_DIR as UID $CURRENT_UID. Mount them writable for this user."
    exec "$@"
  fi
}

# Call the main function to start execution
main "$@"