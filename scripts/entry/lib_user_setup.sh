#!/bin/bash

# Function to determine APP_UID and APP_GID for user/group creation and chown operation
determine_app_ids() {
    # Use UID and GID environment variables if provided, otherwise default to 1000
    local effective_uid_candidate="${UID:-}"
    local effective_gid_candidate="${GID:-}"
    if [ -z "$effective_uid_candidate" ] || [ -z "$effective_gid_candidate" ]; then
        APP_UID="1000"
        APP_GID="1000"
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
                local existing_group_name_at_gid="$(getent group "$APP_GID" | cut -d: -f1)"
                echo "INFO: Desired GID '$APP_GID' is already assigned to group '$existing_group_name_at_gid'."
                echo "INFO: Adapting to use existing group name '$existing_group_name_at_gid' for operations instead of '$APP_GROUP'."
                APP_GROUP="$existing_group_name_at_gid" # Update APP_GROUP to the actual group name found
                _group_setup_for_gosu=true # Mark setup as successful so it proceeds
            else
                # GID is either free, or taken by a group with the same name but wrong GID.
                echo "INFO: Deleting group '$APP_GROUP' to recreate with correct GID."
                delgroup "$APP_GROUP" 2>/dev/null || echo "WARN: Could not delete existing group '$APP_GROUP'. Proceeding but may cause issues."
                echo "INFO: Creating group '$APP_GROUP' (GID: $APP_GID)."
                if addgroup --gid "$APP_GID" "$APP_GROUP"; then
                    _group_setup_for_gosu=true
                else
                    echo "CRITICAL: Failed to create group '$APP_GROUP' with GID '$APP_GID' for unknown reasons. User will not be created/run with custom GID."
                    _group_setup_for_gosu=false
                fi
            fi
        fi
    else # Group name does not exist.
        # Check if GID is taken by any other group.
        if getent group "$APP_GID" >/dev/null; then
            local actual_group_name_at_gid="$(getent group "$APP_GID" | cut -d: -f1)"
            echo "INFO: Desired GID '$APP_GID' is already in use by group '$actual_group_name_at_gid'."
            echo "INFO: Group '$APP_GROUP' (desired name) not found. Adapting to use existing group name '$actual_group_name_at_gid' for operations."
            APP_GROUP="$actual_group_name_at_gid" # Update APP_GROUP to the actual group name found
            _group_setup_for_gosu=true # Mark setup as successful so it proceeds with the existing group
        else
            # GID is free, so create the group with the desired name and GID.
            echo "INFO: Creating group '$APP_GROUP' (GID: $APP_GID)."
            if addgroup --gid "$APP_GID" "$APP_GROUP"; then
                _group_setup_for_gosu=true
            else
                echo "CRITICAL: Failed to create group '$APP_GROUP'. User will not be created/run with custom GID."
                _group_setup_for_gosu=false
            fi
        fi
    fi
}

# Function to set up the application user
setup_user() {
    # Ensure group setup was successful before proceeding with user setup
    if ! $_group_setup_for_gosu; then
        echo "CRITICAL: Group '$APP_GROUP' could not be properly set up for gosu. Skipping user creation."
        _user_setup_for_gosu=false
        return # Exit the function if group setup failed
    fi

    # Check if the user exists by name
    if getent passwd "$APP_USER" >/dev/null; then
        local current_uid_in_passwd="$(id -u "$APP_USER")"
        local current_gid_in_passwd="$(id -g "$APP_USER")"

        # User name exists. Check if UID and primary GID match.
        if [ "$current_uid_in_passwd" = "$APP_UID" ] && [ "$current_gid_in_passwd" = "$APP_GID" ]; then
            echo "INFO: User '$APP_USER' already exists with correct UID/GID ($APP_UID/$APP_GID)."
            _user_setup_for_gosu=true
        else
            # User name exists but with wrong UID/GID.
            echo "WARN: User '$APP_USER' exists but has UID/GID ($current_uid_in_passwd/$current_gid_in_passwd), expected $APP_UID/$APP_GID."

            # Check if desired UID is already taken by another user name.
            if getent passwd "$APP_UID" >/dev/null && [ "$(getent passwd "$APP_UID" | cut -d: -f1)" != "$APP_USER" ]; then
                # Conflict: Desired UID is used by a DIFFERENT user. Adapt to that user.
                local existing_username_at_uid="$(getent passwd "$APP_UID" | cut -d: -f1)"
                local existing_user_gid_at_uid="$(getent passwd "$APP_UID" | cut -d: -f4)"
                local existing_group_name_at_gid="$(getent group "$existing_user_gid_at_uid" | cut -d: -f1)"

                echo "WARN: Desired UID '$APP_UID' (originally for user '$APP_USER') is already in use by another user: '$existing_username_at_uid'."
                echo "INFO: Adapting to use existing user '$existing_username_at_uid' (UID: $APP_UID, GID: $existing_user_gid_at_uid) and their primary group '$existing_group_name_at_gid' for execution."

                # Update the script's global variables to reflect the actual user found
                APP_USER="$existing_username_at_uid"
                APP_GID="$existing_user_gid_at_uid"
                APP_GROUP="$existing_group_name_at_gid"
                _user_setup_for_gosu=true # Mark setup as successful because we've adapted
            else
                # Desired UID is either free, or taken by APP_USER (which is good),
                # but the existing user's UID/GID needs correction.
                echo "INFO: Modifying user '$APP_USER' to match expected UID/GID."
                # Use usermod to update attributes: UID (-u), GID (-g).
                # Home directory will be handled by handle_permissions.
                usermod -u "$APP_UID" -g "$APP_GID" "$APP_USER" || {
                    echo "WARN: usermod failed. Attempting to delete and recreate user '$APP_USER'."
                    deluser "$APP_USER" 2>/dev/null || echo "WARN: Could not delete existing user '$APP_USER'. Proceeding but may cause issues."
                    echo "INFO: Recreating user '$APP_USER' (UID: $APP_UID) in group '$APP_GROUP' with home '$APP_HOME'."
                    if adduser --uid "$APP_UID" --ingroup "$APP_GROUP" \
                            --home "$APP_HOME" --shell /bin/sh \
                            --disabled-password --gecos "" --no-create-home "$APP_USER"; then
                        _user_setup_for_gosu=true
                    else
                        echo "CRITICAL: Failed to recreate user '$APP_USER'. User will not be created/run with custom UID/GID."
                        _user_setup_for_gosu=false
                    fi
                }
                # If modifications/recreation succeeded, ensure flag is true
                if $_user_setup_for_gosu; then
                    _user_setup_for_gosu=true
                fi
            fi
        fi
    else # User name does not exist.
        # Check if desired UID is already taken by another user name.
        if getent passwd "$APP_UID" >/dev/null; then
            # Conflict: Desired UID is used by a DIFFERENT user. Adapt to that user.
            local existing_username_at_uid="$(getent passwd "$APP_UID" | cut -d: -f1)"
            local existing_user_gid_at_uid="$(getent passwd "$APP_UID" | cut -d: -f4)"
            local existing_group_name_at_gid="$(getent group "$existing_user_gid_at_uid" | cut -d: -f1)"

            echo "WARN: Desired UID '$APP_UID' (originally for user '$APP_USER') is already in use by another user: '$existing_username_at_uid'."
            echo "INFO: Group '$APP_USER' (desired name) not found. Adapting to use existing user '$existing_username_at_uid' (UID: $APP_UID, GID: $existing_user_gid_at_uid) and their primary group '$existing_group_name_at_gid' for execution."

            # Update the script's global variables to reflect the actual user found
            APP_USER="$existing_username_at_uid"
            APP_GID="$existing_user_gid_at_uid"
            APP_GROUP="$existing_group_name_at_gid"
            _user_setup_for_gosu=true # Mark setup as successful because we've adapted
        else
            # User name does not exist, and UID is free. Create the user.
            echo "INFO: Creating user '$APP_USER' (UID: $APP_UID) in group '$APP_GROUP' with home '$APP_HOME'."
            if adduser --uid "$APP_UID" --ingroup "$APP_GROUP" \
                    --home "$APP_HOME" --shell /bin/sh \
                    --disabled-password --gecos "" --no-create-home "$APP_USER"; then
                _user_setup_for_gosu=true
            else
                echo "CRITICAL: Failed to create user '$APP_USER'. User will not be created/run with custom UID/GID."
                _user_setup_for_gosu=false
            fi
        fi
    fi    

}