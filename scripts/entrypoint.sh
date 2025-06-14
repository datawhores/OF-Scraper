#!/bin/sh
set -e

# Set default user if not provided via environment variables
TARGET_USER=${USER_NAME:-john}
TARGET_GROUP=${GROUP_NAME:-${TARGET_USER}}
TARGET_UID=${USER_ID:-1000}
TARGET_GID=${GROUP_ID:-1000}

echo "--- Entrypoint: Starting up as user '$TARGET_USER' with UID $TARGET_UID ---"

# Create group and user on the fly
addgroup --gid "$TARGET_GID" "$TARGET_GROUP" >/dev/null 2>&1 || true
adduser --uid "$TARGET_UID" --ingroup "$TARGET_GROUP" --home "/home/$TARGET_USER" --shell /bin/sh --disabled-password --gecos "" --no-create-home "$TARGET_USER" >/dev/null 2>&1 || true

# Create home directory and ensure it's owned by the target user
# This is crucial for handling mounted volumes correctly.
mkdir -p "/home/$TARGET_USER"
chown -R "$TARGET_UID:$TARGET_GID" "/home/$TARGET_USER"

# Drop root privileges and execute the main command ("$@") as the target user
echo "--- Entrypoint: Switching to user '$TARGET_USER' and running command: $@ ---"
exec gosu "$TARGET_USER" "$@"