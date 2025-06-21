
# Function to install Python packages conditionally
install_python_deps_conditionally() {
    # Check if SKIP_FFMPEG is explicitly set to 'true'
    if [ "${SKIP_FFMPEG:-false}" = "true" ]; then
        echo "INFO: SKIP_FFMPEG environment variable is set to 'true'. Skipping pyffmpeg Python package installation."
    # If not skipped and running as non-root (i.e., we'll gosu to APP_USER)
    elif [ "$CURRENT_UID" -ne 0 ]; then
        echo "INFO: SKIP_FFMPEG environment variable is set to 'false'. Attempting to install pyffmpeg Python package (with gosu)."
        # Install the Python wrapper package using gosu to the application user
        gosu "$APP_USER" uv pip install pyffmpeg==2.4.2.20
        echo "INFO: pyffmpeg Python package installation attempted (with gosu)."
    else # This 'else' covers the case where SKIP_FFMPEG is false AND running as root
        echo "INFO: SKIP_FFMPEG environment variable is set to 'false'. Attempting to install pyffmpeg Python package (without gosu)."
        # Install the Python wrapper package as root (e.g., during build stage, or if gosu fails later)
        uv pip install pyffmpeg==2.4.2.20
        echo "INFO: pyffmpeg Python package installation attempted (without gosu)."    
    fi
}