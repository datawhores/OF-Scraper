#!/bin/bash
set -euo pipefail

# --- Configuration Variables ---
APP_USER="${USERNAME:-ofscraper}"
APP_GROUP="${GROUPNAME:-$APP_USER}"
APP_HOME="/home/$APP_USER"
DATA_DIR="/data"
CONFIG_DIR="/config"

export HOME="$APP_HOME"

CURRENT_UID="$(id -u)"

# Global flags to indicate if user/group could be set up for gosu
_group_setup_for_gosu=false
_user_setup_for_gosu=false

# Global APP_UID and APP_GID (will be set by determine_app_ids)
APP_UID=""
APP_GID=""
#For some reason we need to run this at runtime
# python3 -c 'from pyffmpeg import FFmpeg;'

# Function to install Python packages conditionally
install_python_deps_conditionally() {
    if [ "${INSTALL_FFMPEG:-false}" = "true" ]; then
        echo "INFO: INSTALL_FFMPEG environment variable is set to 'true'. Attempting to install pyffmpeg Python package."
        # This installs the Python wrapper package.
        # Note: This package typically requires a system-level ffmpeg executable to function.
        # If you encounter issues, you may need to install the 'ffmpeg' system package.
        uv pip install pyffmpeg==2.4.2.20
        echo "INFO: pyffmpeg Python package installation attempted."
    else
        echo "INFO: INSTALL_FFMPEG environment variable is not set to 'true'. Skipping pyffmpeg Python package installation."
    fi
}

# Function to check for user namespace remapping (e.g., from --userns=keep-id or --userns-remap)
is_userns_remapped() {
    # Check /proc/self/uid_map for non-default mapping.
    # A default (no remapping) looks like: "0          0 4294967295"
    # If it deviates, remapping is active.
    ! grep -qE '^0\s+0\s+4294967295$' /proc/self/uid_map 2>/dev/null
}

# Function to determine APP_UID and APP_GID for user/group creation and chown operation
determine_app_ids() {
    # Fix for unbound variable: use :- to assign empty string if variable is unset
    local effective_uid_candidate="${UID:-}"
    local effective_gid_candidate="${GID:-}"

    if [ -z "$effective_uid_candidate" ] || [ -z "$effective_gid_candidate" ]; then
        # UID or GID were NOT explicitly provided as environment variables
        if is_userns_remapped; then
            echo "WARN: User namespace remapping detected (e.g., via --userns=keep-id or --userns-remap)."
            echo "WARN: Neither UID nor GID environment variables were explicitly provided."
            echo "WARN: This means files created will be owned by UID/GID 1000 on the host."
            echo "WARN: If your host user has a different UID/GID (e.g., 1002), these files will not be owned by you."
            echo "WARN: To ensure correct file ownership, please set UID and GID when running the container:"
            echo "WARN:   docker run -e UID=\$(id -u) -e GID=\$(id -g) ..."
            echo "INFO: Defaulting to UID 1000 and GID 1000 for user/group creation and file ownership."
            APP_UID="1000"
            APP_GID="1000"
        else
            # Not remapped, and no UID/GID provided. Default to 1000.
            echo "INFO: UID and/or GID not set. Defaulting to UID 1000 and GID 1000."
            APP_UID="1000"
            APP_GID="1000"
        fi
    else
        echo "INFO: Using provided UID ($effective_uid_candidate) and GID ($effective_gid_candidate)."
        APP_UID="$effective_uid_candidate"
        APP_GID="$effective_gid_candidate"
    fi
}

# Function to set up the application group
setup_group() {
    if getent group "$APP_GROUP" >/dev/null; then
        # Group name exists. Check if GID matches.
        if [ "$(id -g "$APP_GROUP")" = "$APP_GID" ]; then
            echo "INFO: Group '$APP_GROUP' already exists with correct GID ($APP_GID)."
            _group_setup_for_gosu=true
        else
            # Group name exists but with wrong GID.
            echo "WARN: Group '$APP_GROUP' exists but has GID $(id -g "$APP_GROUP"), expected $APP_GID."
            # Check if desired GID is already taken by another group name.
            if getent group "$APP_GID" >/dev/null && [ "$(getent group "$APP_GID" | cut -d: -f1)" != "$APP_GROUP" ]; then
                echo "ERROR: Desired GID '$APP_GID' is already in use by another group: $(getent group "$APP_GID" | cut -d: -f1)."
                echo "INFO: Group setup for '$APP_GROUP' with GID '$APP_GID' abandoned due to conflict. User will not be created/run with custom GID."
                _group_setup_for_gosu=false # Ensure it's false
            else
                echo "INFO: Deleting group '$APP_GROUP' to recreate with correct GID."
                delgroup "$APP_GROUP" 2>/dev/null || echo "WARN: Could not delete existing group '$APP_GROUP'. Proceeding but may cause issues."
                echo "INFO: Creating group '$APP_GROUP' (GID: $APP_GID)."
                if addgroup --gid "$APP_GID" "$APP_GROUP"; then
                    _group_setup_for_gosu=true
                else
                    echo "CRITICAL: Failed to create group '$APP_GROUP' with GID '$APP_GID' for unknown reasons. User will not be created/run with custom GID."
                    # No exit, _group_setup_for_gosu remains false
                fi
            fi
        fi
    else
        # Group name does not exist. Check if GID is taken.
        if getent group "$APP_GID" >/dev/null; then
            echo "ERROR: Desired GID '$APP_GID' is already in use by another group: $(getent group "$APP_GID" | cut -d: -f1)."
            echo "INFO: Group setup for '$APP_GROUP' with GID '$APP_GID' abandoned due to conflict. User will not be created/run with custom GID."
            _group_setup_for_gosu=false # Ensure it's false
        else
            echo "INFO: Creating group '$APP_GROUP' (GID: $APP_GID)."
            if addgroup --gid "$APP_GID" "$APP_GROUP"; then
                _group_setup_for_gosu=true
            else
                echo "CRITICAL: Failed to create group '$APP_GROUP' with GID '$APP_GID' for unknown reasons. User will not be created/run with custom GID."
                # No exit, _group_setup_for_gosu remains false
            fi
        fi
    fi
}

# Function to set up the application user
setup_user() {
    if $_group_setup_for_gosu; then
        if getent passwd "$APP_USER" >/dev/null; then
            # User name exists. Check if UID and primary GID match.
            if [ "$(id -u "$APP_USER")" = "$APP_UID" ] && [ "$(id -g "$APP_USER")" = "$APP_GID" ]; then
                echo "INFO: User '$APP_USER' already exists with correct UID/GID ($APP_UID/$APP_GID)."
                _user_setup_for_gosu=true
            else
                # User name exists but with wrong UID/GID.
                echo "WARN: User '$APP_USER' exists but has UID $(id -u "$APP_USER")/GID $(id -g "$APP_USER"), expected $APP_UID/$APP_GID."
                # Check if desired UID is already taken by another user name.
                if getent passwd "$APP_UID" >/dev/null && [ "$(getent passwd "$APP_UID" | cut -d: -f1)" != "$APP_USER" ]; then
                    echo "ERROR: Desired UID '$APP_UID' is already in use by another user: $(getent passwd "$APP_UID" | cut -d: -f1)."
                    echo "INFO: User setup for '$APP_USER' with UID '$APP_UID' abandoned due to conflict. User will not be created/run with custom UID/GID."
                    _user_setup_for_gosu=false # Ensure it's false
                else
                    echo "INFO: Deleting user '$APP_USER' to recreate with correct UID/GID."
                    deluser "$APP_USER" 2>/dev/null || echo "WARN: Could not delete existing user '$APP_USER'. Proceeding but may cause issues."
                    echo "INFO: Creating user '$APP_USER' (UID: $APP_UID) in group '$APP_GROUP'."
                    if adduser --uid "$APP_UID" --ingroup "$APP_GROUP" \
                            --home "$APP_HOME" --shell /bin/sh \
                            --disabled-password --gecos "" --no-create-home "$APP_USER"; then
                        _user_setup_for_gosu=true
                    else
                        echo "CRITICAL: Failed to create user '$APP_USER' with UID '$APP_UID' in group '$APP_GROUP' for unknown reasons. User will not be created/run with custom UID/GID."
                        # No exit, _user_setup_for_gosu remains false
                    fi
                fi
            fi
        else
            # User name does not exist. Check if UID is taken.
            if getent passwd "$APP_UID" >/dev/null; then
                echo "ERROR: Desired UID '$APP_UID' is already in use by another user: $(getent passwd "$APP_UID" | cut -d: -f1)."
                echo "INFO: User setup for '$APP_USER' with UID '$APP_UID' abandoned due to conflict. User will not be created/run with custom UID/GID."
                _user_setup_for_gosu=false # Ensure it's false
            else
                echo "INFO: Creating user '$APP_USER' (UID: $APP_UID) in group '$APP_GROUP'."
                if adduser --uid "$APP_UID" --ingroup "$APP_GROUP" \
                        --home "$APP_HOME" --shell /bin/sh \
                        --disabled-password --gecos "" --no-create-home "$APP_USER"; then
                    _user_setup_for_gosu=true
                else
                    echo "CRITICAL: Failed to create user '$APP_USER' with UID '$APP_UID' in group '$APP_GROUP' for unknown reasons. User will not be created/run with custom UID/GID."
                    # No exit, _user_setup_for_gosu remains false
                fi
            fi
        fi
    else
        echo "CRITICAL: Group '$APP_GROUP' could not be properly set up for gosu. Skipping user creation."
        # _user_setup_for_gosu remains false.
    fi
}


# Function to handle directory creation and permissions
handle_permissions() {
    echo "Making $APP_HOME, $DATA_DIR, and $CONFIG_DIR."
    mkdir -p "$APP_HOME"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$DATA_DIR"

  
    # Check if UID was explicitly set (indicating the user provided valid IDs)
    if [ -n "${UID:-}" ] && [ -n "${GID:-}" ]; then
        # User IDs were provided, so we assume APP_UID/GID are correct for host.
        echo "INFO: Ensuring permissions for $APP_HOME, $DATA_DIR, and $CONFIG_DIR using provided IDs."
        chown -R "$APP_USER:$APP_GROUP" "$APP_HOME" || echo "WARN: Could not chown $APP_HOME to $APP_USER:$APP_GROUP. Permissions may be incorrect."
        chown -R "$APP_USER:$APP_GROUP" "$CONFIG_DIR" || echo "WARN: Could not chown $CONFIG_DIR to $APP_USER:$APP_GROUP. Permissions may be incorrect."
        chown -R "$APP_USER:$APP_GROUP" "$DATA_DIR" || echo "WARN: Could not chown $DATA_DIR to $APP_USER:$APP_GROUP. Permissions may be incorrect."
    elif ! is_userns_remapped; then
        # No UID provided AND no userns remapping: default to 1000, which is often host user 1.
        echo "INFO: Ensuring permissions for $APP_HOME, $DATA_DIR, and $CONFIG_DIR using default IDs (no remapping)."
        chown -R "$APP_USER:$APP_GROUP" "$APP_HOME" || echo "WARN: Could not chown $APP_HOME to $APP_USER:$APP_GROUP. Permissions may be incorrect."
        chown -R "$APP_USER:$APP_GROUP" "$CONFIG_DIR" || echo "WARN: Could not chown $CONFIG_DIR to $APP_USER:$APP_GROUP. Permissions may be incorrect."
        chown -R "$APP_USER:$APP_GROUP" "$DATA_DIR" || echo "WARN: Could not chown $DATA_DIR to $APP_USER:$APP_GROUP. Permissions may be incorrect."
    else
        # No UID provided AND userns remapping IS active: highly ambiguous.
        # In this case, your current "WARNING: Not changing permissions" is prudent.
        echo "WARNING: Not changing permissions for $APP_HOME, $DATA_DIR, and $CONFIG_DIR."
        echo "WARNING: File ownership might be misaligned with host user. See earlier warnings about UID/GID."
    fi
}

# Main execution logic
main() {
    if [ "$CURRENT_UID" -eq 0 ]; then
        determine_app_ids
        setup_group
        setup_user
        handle_permissions
        install_python_deps_conditionally 
        ls -la /home/ofscraper


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
        echo "INFO: Running as non-root (UID: $CURRENT_UID). Executing command as current user: $*"
        # Ensure the target home, data, and config directories exist, but don't change ownership if not root
        mkdir -p "$APP_HOME" "$DATA_DIR" "$CONFIG_DIR"
        exec "$@"
    fi
}

# Call the main function to start execution
main "$@"