import os

def load_like_config():
    """
    Loads 'like' related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded 'like' configuration settings.
    """
    config = {}

    # --- Like Feature Configuration ---
    # MAX_SLEEP_DURATION_LIKE: Maximum sleep duration for like operations (seconds)
    # Default: 1.5
    config['MAX_SLEEP_DURATION_LIKE'] = float(os.getenv('MAX_SLEEP_DURATION_LIKE', '1.5'))

    # MIN_SLEEP_DURATION_LIKE: Minimum sleep duration for like operations (seconds)
    # Default: 0.9
    config['MIN_SLEEP_DURATION_LIKE'] = float(os.getenv('MIN_SLEEP_DURATION_LIKE', '0.9'))

    # SESSION_429_LIKE_INCREASE_SLEEP_TIME_DIF: Difference to increase sleep time on 429 for like operations
    # Default: 0
    config['SESSION_429_LIKE_INCREASE_SLEEP_TIME_DIF'] = int(os.getenv('SESSION_429_LIKE_INCREASE_SLEEP_TIME_DIF', '0'))

    # SESSION_429_SLEEP_STARTER_VAL: Starting sleep value for 429 errors in like operations (seconds)
    # Default: 8
    config['SESSION_429_LIKE_SLEEP_STARTER_VAL'] = int(os.getenv('SESSION_429_SLEEP_LIKE_STARTER_VAL', '8'))

    # LIKE_MAX_RETRIES: Maximum number of retries for failed like operations
    # Default: 5
    config['LIKE_MAX_RETRIES'] = int(os.getenv('LIKE_MAX_RETRIES', '5'))
    
    # DOUBLE_TOGGLE_SLEEP_DURATION_LIKE: Sleep duration in seconds for double toggle like operations
    # Default: 5
    config['DOUBLE_TOGGLE_SLEEP_DURATION_LIKE'] = int(os.getenv('DOUBLE_TOGGLE_SLEEP_DURATION_LIKE', '5'))    
    
    return config