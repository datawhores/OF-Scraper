#!/bin/sh
set -e

# Set default values or use environment variables if provided
TARGET_USER=${USER_NAME:-ofscraper}
TARGET_GROUP=${GROUP_NAME:-${TARGET_USER}}
TARGET_UID=${USER_ID:-1000}
TARGET_GID=${GROUP_ID:-1000}

# Create group and user on the fly
addgroup --gid "$TARGET_GID" "$TARGET_GROUP" >/dev/null 2>&1 || true
adduser --uid "$TARGET_UID" --ingroup "$TARGET_GROUP" --home "/home/$TARGET_USER" --shell /bin/sh --disabled-password --gecos "" --no-create-home "$TARGET_USER" >/dev/null 2>&1 || true

# Create home directory and ensure correct ownership for mounted volumes
mkdir -p "/home/$TARGET_USER"
# Drop root privileges and execute the main command as the target user
exec gosu "$TARGET_USER" "$@"