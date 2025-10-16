import os


def load_cdm_config():
    """
    Loads CDM (Content Decryption Module) related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded CDM configuration settings.
    """
    config = {}

    # --- CDM Configuration ---
    # CDM_TEST_TIMEOUT: Timeout for CDM tests (seconds).
    # Default: 30
    config["CDM_TEST_TIMEOUT"] = int(os.getenv("OFSC_CDM_TEST_TIMEOUT", "30"))

    # CDM_TIMEOUT: General timeout for CDM operations (seconds).
    # Default: 40
    config["CDM_TIMEOUT"] = int(os.getenv("OFSC_CDM_TIMEOUT", "40"))

    # CDM_MIN_WAIT: Minimum wait time before retrying a CDM operation (seconds).
    # Default: 1.5
    config["CDM_MIN_WAIT"] = float(os.getenv("OFSC_CDM_MIN_WAIT", "1.5"))

    # CDM_MAX_WAIT: Maximum wait time before retrying a CDM operation (seconds).
    # Default: 6
    config["CDM_MAX_WAIT"] = float(os.getenv("OFSC_CDM_MAX_WAIT", "6"))

    # CDM_NUM_TRIES: Number of retries for general CDM operations.
    # Default: 8
    config["CDM_NUM_TRIES"] = int(os.getenv("OFSC_CDM_NUM_TRIES", "8"))

    # CDM_NUM_TRIES_CHECK: Number of retries for CDM checks.
    # Default: 1
    config["CDM_NUM_TRIES_CHECK"] = int(os.getenv("OFSC_CDM_NUM_TRIES_CHECK", "1"))

    # CDM_TEST_NUM_TRIES: Number of retries for CDM tests.
    # Default: 2
    config["CDM_TEST_NUM_TRIES"] = int(os.getenv("OFSC_CDM_TEST_NUM_TRIES", "2"))

    return config
