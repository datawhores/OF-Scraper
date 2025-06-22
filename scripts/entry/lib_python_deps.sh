
# Function to install Python packages conditionally
install_python_deps_conditionally() {
    # Check if SKIP_FFMPEG is explicitly set to 'true'
    if [ "${SKIP_FFMPEG:-false}" = "true" ]; then
        echo "INFO: SKIP_FFMPEG environment variable is set to 'true'. Skipping pyffmpeg Python package installation."
    # If not skipped and running as root
    elif [ "$CURRENT_UID" -eq 0 ]; then # SKIP_FFMPEG is false AND running as root
        echo "INFO: SKIP_FFMPEG environment variable is set to 'false'. Attempting to install pyffmpeg Python package in venv."
        # Install the Python wrapper package as root (e.g., during build stage, or if gosu fails later)
        uv pip install pyffmpeg==2.4.2.20
        echo "INFO: pyffmpeg Python package installation attempted (without gosu)."
    else
        echo "ERROR: Cannot install dependencies into /app/.venv. We are not running as root."
        exit 1
    fi
}