#!/bin/bash
# .github/scripts/retry_action.sh

set -euo pipefail

# This script will retry a GitHub Action command.
# Usage: retry_action.sh <max_attempts> <sleep_seconds> <action_command_with_inputs...>
# Example: retry_action.sh 3 10 "actions/upload-artifact@v4 name:my-artifact path:./build"

MAX_ATTEMPTS="${1:-3}" # Default 3 attempts if not provided
SLEEP_SECONDS="${2:-10}" # Default 10 seconds sleep if not provided
shift 2 # Shift arguments to get the actual command

ACTION_COMMAND="$@" # The rest of the arguments form the action call

echo "Attempting to run action (max $MAX_ATTEMPTS attempts, $SLEEP_SECONDS sec delay): '$ACTION_COMMAND'" >&2

ATTEMPT_NUM=1
until eval "$ACTION_COMMAND"; do # Use eval to correctly parse the action command with its inputs
    EXIT_CODE=$?
    if [ "$ATTEMPT_NUM" -ge "$MAX_ATTEMPTS" ]; then
        echo "ERROR: Action failed after $MAX_ATTEMPTS attempts." >&2
        exit "$EXIT_CODE" # Exit with the last command's failure code
    fi
    echo "Action failed (exit code $EXIT_CODE). Retrying in $SLEEP_SECONDS seconds... (Attempt $ATTEMPT_NUM of $MAX_ATTEMPTS)" >&2
    sleep "$SLEEP_SECONDS"
    ATTEMPT_NUM=$((ATTEMPT_NUM + 1))
done

echo "Action succeeded on attempt $ATTEMPT_NUM." >&2
exit 0 # Indicate success