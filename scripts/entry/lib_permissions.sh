#!/bin/bash

# Function to handle directory creation and permissions
handle_permissions() {
    # Verify that group and user setup were successful before proceeding with permissions
    if ! $_group_setup_for_gosu || ! $_user_setup_for_gosu; then
        echo "WARN: Skipping directory/permission setup as group or user setup failed."
        return 1 # Indicate failure
    fi

    # CRITICAL: Ensure the user's home directory in /etc/passwd is correctly set.
    # This must run BEFORE gosu is called, as gosu reads /etc/passwd.
    # This handles cases where APP_USER was an existing user with a wrong home path.
    local current_home_in_passwd="$(getent passwd "$APP_USER" | cut -d: -f6)"
    if [ "$current_home_in_passwd" != "$APP_HOME" ]; then
        echo "INFO: Ensuring user '$APP_USER' home directory in /etc/passwd is '$APP_HOME' (was '$current_home_in_passwd')."
        usermod -d "$APP_HOME" "$APP_USER" || {
            echo "ERROR: Failed to switch home directory for '$APP_USER' in /etc/passwd. This may cause issues with applications."
            APP_HOME=$current_home_in_passwd # Fallback: if usermod fails, use the old home to prevent errors with mkdir/chown
        }
    else
        echo "INFO: User '$APP_USER' home directory in /etc/passwd is already correct: '$APP_HOME'."
    fi

    echo "INFO: Making $APP_HOME, $DATA_DIR, and $CONFIG_DIR."
    mkdir -p "$APP_HOME"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$DATA_DIR"

    # Handle ownership based on KEEP_PERM or provided UID/GID
    if [ "${KEEP_PERM:-false}" = "true" ]; then 
        echo "INFO: Not changing permissions for $APP_HOME, $DATA_DIR, and $CONFIG_DIR due to KEEP_PERM=true."
    elif [ -n "${UID:-}" ] && [ -n "${GID:-}" ]; then 
        # User IDs were provided, so we assume APP_UID/GID are correct for host.
        echo "INFO: Ensuring permissions for $APP_HOME, $DATA_DIR, and $CONFIG_DIR using provided IDs."
        chown -R "$APP_USER:$APP_GROUP" "$APP_HOME" || echo "WARN: Could not chown $APP_HOME to $APP_USER:$APP_GROUP. Permissions may be incorrect."
        chown -R "$APP_USER:$APP_GROUP" "$CONFIG_DIR" || echo "WARN: Could not chown $CONFIG_DIR to $APP_USER:$APP_GROUP. Permissions may be incorrect."
        chown -R "$APP_USER:$APP_GROUP" "$DATA_DIR" || echo "WARN: Could not chown $DATA_DIR to $APP_USER:$APP_GROUP. Permissions may be incorrect."
    else
        # No UID/GID provided, so use the determined APP_USER/APP_GROUP
        echo "INFO: Ensuring permissions for $APP_HOME, $DATA_DIR, and $CONFIG_DIR using default (or adapted) user/group."
        chown -R "$APP_USER:$APP_GROUP" "$APP_HOME" || echo "WARN: Could not chown $APP_HOME to "$APP_USER:$APP_GROUP". Permissions may be incorrect."
        chown -R "$APP_USER:$APP_GROUP" "$CONFIG_DIR" || echo "WARN: Could not chown $CONFIG_DIR to "$APP_USER:$APP_GROUP". Permissions may be incorrect."
        chown -R "$APP_USER:$APP_GROUP" "$DATA_DIR" || echo "WARN: Could not chown $DATA_DIR to "$APP_USER:$APP_GROUP". Permissions may be incorrect."
        #chown app folder
        chown -R "$APP_USER:$APP_GROUP" "/app" || echo "WARN: Could not chown /app to "$APP_USER:$APP_GROUP". Permissions may be incorrect."

    fi 
}