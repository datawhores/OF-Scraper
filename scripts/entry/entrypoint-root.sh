#!/bin/bash
set -euo pipefail

# --- Configuration Variables ---
# Default user details for the application. These can be overridden by environment variables.
# Using 'ofscraper' as default for both user and group for simplicity and common practice.
APP_USER="${USERNAME:-ofscraper}"
APP_GROUP="${GROUPNAME:-$APP_USER}"
APP_UID="${USER_ID:-1000}"
APP_GID="${GROUP_ID:-1000}"
APP_HOME="/home/$APP_USER"


#set home
export HOME="$APP_HOME"


# --- Determine Current User ---
CURRENT_UID="$(id -u)"

# --- Privilege Management ---
if [ "$CURRENT_UID" -eq 0 ]; then
    # Running as root: Set up user and drop privileges
    echo "INFO: Running as root (UID 0). Setting up user and permissions for '$APP_USER'."

    # Create group if it doesn't exist
    if ! getent group "$APP_GROUP" >/dev/null; then
        echo "INFO: Creating group '$APP_GROUP' (GID: $APP_GID)."
        addgroup --gid "$APP_GID" "$APP_GROUP"
    fi

    # Create user if it doesn't exist
    if ! getent passwd "$APP_USER" >/dev/null; then
        echo "INFO: Creating user '$APP_USER' (UID: $APP_UID) in group '$APP_GROUP'."
        adduser --uid "$APP_UID" --ingroup "$APP_GROUP" \
                --home "$APP_HOME" --shell /bin/sh \
                --disabled-password --gecos "" --no-create-home "$APP_USER"
    fi

    # Ensure the home directory exists and has correct ownership
    echo "INFO: Giving $APP_USER Permession on $APP_HOME"
    mkdir -p "$APP_HOME"
    chown -R "$APP_USER:$APP_GROUP" "$APP_HOME"
    

    echo "INFO: Dropping privileges to user '$APP_USER' (UID: $APP_UID) and executing command: $*"
    exec gosu "$APP_USER" "$@"
else
    # Running as non-root: Use existing user
    echo "INFO: Running as non-root (UID: $CURRENT_UID). Executing command as current user: $*"
    # Ensure the target home directory exists, but don't change ownership if not root
    mkdir -p "$APP_HOME"
    exec "$@"
fi