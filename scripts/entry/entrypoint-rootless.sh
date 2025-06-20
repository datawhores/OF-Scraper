#!/bin/bash
set -euo pipefail

# 1. Determine the actual user running the process
CURRENT_USER=$(whoami 2>/dev/null || echo "ofscraper") # Renamed fallback for clarity

# 2. Define the base for the HOME directory
#    - Priority 1: Use OF_HOME environment variable if set by the user
#    - Priority 2: Default to /home/${CURRENT_USER}
#    - Priority 3: Fallback to /app if CURRENT_USER is not meaningful (e.g., just a UID)
if [ -n "${OF_HOME:-}" ]; then
    export HOME="${OF_HOME}"
    echo "INFO: Using custom HOME environment variable: ${HOME}"
elif [ "${CURRENT_USER}" != "ofscraper_user" ]; then # If whoami returned a real username
    export HOME="/home/${CURRENT_USER}"
    echo "INFO: Using default HOME environment variable for user '${CURRENT_USER}': ${HOME}"
else # Fallback if whoami couldn't determine a named user
    export HOME="/app" # A sensible default if no specific user home can be determined
    echo "INFO: Using default HOME environment variable: ${HOME} (no named user detected)"
fi

echo "DEBUG: Current PID 1 (Entrypoint) starting as UID: $(id -u), User: ${CURRENT_USER}"
echo "DEBUG: Setting HOME environment variable to ${HOME}" # Updated debug message

# 3. Create necessary subdirectories relative to the determined HOME
mkdir -p "${HOME}/.config/ofscraper/"
mkdir -p "${HOME}/Data"
echo "INFO: Executing command as user ${CURRENT_USER}: $@"
exec "$@"