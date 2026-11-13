#!/bin/bash

set_up_all_paths() {
    set_up_mount_paths
}

set_up_mount_paths() {
    set_data_dir_path
    set_config_dir_path
}
# Function to set DATA_DIR.
# This function relies on: APP_HOME
set_data_dir_path() {
    # If the DATA_DIR environment variable is unset or empty,
    # default to a 'data' directory relative to APP_HOME.
    if [ -z "${DATA_DIR-}" ]; then # Checking the current value of DATA_DIR (which would be unset/empty if not provided as ENV var)
        DATA_DIR="$APP_HOME/data"
    fi
    # Save downloads into DATA_DIR (the mounted folder) unless told otherwise.
    # The app's own default, ~/Data/ofscraper, is a different folder on a
    # case-sensitive filesystem, so downloads stayed inside the container.
    # The image sets OFSC_SAVE_PATH_DEFAULT to $APP_HOME/data; follow a custom
    # DATA_DIR unless the save path was also set explicitly.
    if [ -z "${OFSC_SAVE_PATH_DEFAULT-}" ] || [ "$OFSC_SAVE_PATH_DEFAULT" = "$APP_HOME/data" ]; then
        export OFSC_SAVE_PATH_DEFAULT="$DATA_DIR"
    fi
}

# Function to set CONFIG_DIR.
# This function relies on: APP_HOME
set_config_dir_path() {
    # If the CONFIG_DIR environment variable is unset or empty,
    # default to a '.config' (hidden) directory relative to APP_HOME.
    if [ -z "${CONFIG_DIR-}" ]; then # Checking the current value of CONFIG_DIR (which would be unset/empty if not provided as ENV var)
        CONFIG_DIR="$APP_HOME/.config" # Using .config as requested
    fi
}