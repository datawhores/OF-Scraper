import ofscraper.utils.of_env.of_env as env
from ofscraper.managers.sessionmanager.sessionmanager import SessionSleep


rate_limit_session_sleeper = SessionSleep(
    sleep=env.getattr("SESSION_SLEEP_INIT"),
    min_sleep=env.getattr("SESSION_MIN_SLEEP"),
    difmin=env.getattr("SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("SESSION_SLEEP_MAX"),
    decay_threshold=env.getattr("SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("SESSION_SLEEP_INCREASE_FACTOR"),
    error_name="SESSION_RATE_LIMIT",
)

forbidden_session_sleeper = SessionSleep(
    sleep=env.getattr("SESSION_403_SLEEP_INIT"),
    min_sleep=env.getattr("SESSION_403_MIN_SLEEP"),
    difmin=env.getattr("SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("SESSION_403_SLEEP_MAX"),
    decay_threshold=env.getattr("SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("SESSION_403_SLEEP_INCREASE_FACTOR"),
    error_name="SESSION_403",
)

download_rate_limit_session_sleeper = SessionSleep(
    sleep=env.getattr("DOWNLOAD_SESSION_SLEEP_INIT"),
    min_sleep=env.getattr("DOWNLOAD_SESSION_MIN_SLEEP"),
    difmin=env.getattr("DOWNLOAD_SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("DOWNLOAD_SESSION_SLEEP_MAX"),
    decay_threshold=env.getattr("DOWNLOAD_SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("DOWNLOAD_SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("DOWNLOAD_SESSION_SLEEP_INCREASE_FACTOR"),
    error_name="DOWNLOAD_SESSION_RATE_LIMIT",
)

download_forbidden_session_sleeper = SessionSleep(
    sleep=env.getattr("DOWNLOAD_SESSION_403_SLEEP_INIT"),
    min_sleep=env.getattr("DOWNLOAD_SESSION_403_MIN_SLEEP"),
    difmin=env.getattr("DOWNLOAD_SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("DOWNLOAD_SESSION_403_SLEEP_MAX"),
    decay_threshold=env.getattr("DOWNLOAD_SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("DOWNLOAD_SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("DOWNLOAD_SESSION_403_SLEEP_INCREASE_FACTOR"),
    error_name="DOWNLOAD_SESSION_403",
)

cdm_rate_limit_session_sleeper = SessionSleep(
    sleep=env.getattr("CDM_SESSION_SLEEP_INIT"),
    min_sleep=env.getattr("CDM_SESSION_MIN_SLEEP"),
    difmin=env.getattr("CDM_SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("CDM_SESSION_SLEEP_MAX"),
    decay_threshold=env.getattr("CDM_SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("CDM_SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("CDM_SESSION_SLEEP_INCREASE_FACTOR"),
    error_name="CDM_SESSION_RATE_LIMIT",
)

cdm_forbidden_session_sleeper = SessionSleep(
    sleep=env.getattr("CDM_SESSION_403_SLEEP_INIT"),
    min_sleep=env.getattr("CDM_SESSION_403_MIN_SLEEP"),
    difmin=env.getattr("CDM_SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("CDM_SESSION_403_SLEEP_MAX"),
    decay_threshold=env.getattr("CDM_SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("CDM_SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("CDM_SESSION_403_SLEEP_INCREASE_FACTOR"),
    error_name="CDM_SESSION_403",
)

like_rate_limit_session_sleeper = SessionSleep(
    sleep=env.getattr("LIKE_SESSION_SLEEP_INIT"),
    min_sleep=env.getattr("LIKE_SESSION_MIN_SLEEP"),
    difmin=env.getattr("LIKE_SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("LIKE_SESSION_SLEEP_MAX"),
    decay_threshold=env.getattr("LIKE_SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("LIKE_SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("LIKE_SESSION_SLEEP_INCREASE_FACTOR"),
    error_name="LIKE_SESSION_RATE_LIMIT",
)

like_forbidden_session_sleeper = SessionSleep(
    sleep=env.getattr("LIKE_SESSION_403_SLEEP_INIT"),
    min_sleep=env.getattr("LIKE_SESSION_403_MIN_SLEEP"),
    difmin=env.getattr("LIKE_SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("LIKE_SESSION_403_SLEEP_MAX"),
    decay_threshold=env.getattr("LIKE_SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("LIKE_SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("LIKE_SESSION_403_SLEEP_INCREASE_FACTOR"),
    error_name="LIKE_SESSION_403",
)

metadata_rate_limit_session_sleeper = SessionSleep(
    sleep=env.getattr("METADATA_SESSION_SLEEP_INIT"),
    min_sleep=env.getattr("METADATA_SESSION_MIN_SLEEP"),
    difmin=env.getattr("METADATA_SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("METADATA_SESSION_SLEEP_MAX"),
    decay_threshold=env.getattr("METADATA_SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("METADATA_SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("METADATA_SESSION_SLEEP_INCREASE_FACTOR"),
    error_name="METADATA_SESSION_RATE_LIMIT",
)

metadata_forbidden_session_sleeper = SessionSleep(
    sleep=env.getattr("METADATA_SESSION_403_SLEEP_INIT"),
    min_sleep=env.getattr("METADATA_SESSION_403_MIN_SLEEP"),
    difmin=env.getattr("METADATA_SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("METADATA_SESSION_403_SLEEP_MAX"),
    decay_threshold=env.getattr("METADATA_SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("METADATA_SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("METADATA_SESSION_403_SLEEP_INCREASE_FACTOR"),
    error_name="METADATA_SESSION_403",
)
discord_rate_limit_session_sleeper = SessionSleep(
    sleep=env.getattr("DISCORD_SESSION_SLEEP_INIT"),
    min_sleep=env.getattr("DISCORD_SESSION_MIN_SLEEP"),
    difmin=env.getattr("DISCORD_SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("DISCORD_SESSION_SLEEP_MAX"),
    decay_threshold=env.getattr("DISCORD_SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("DISCORD_SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("DISCORD_SESSION_SLEEP_INCREASE_FACTOR"),
    error_name="DISCORD_SESSION_RATE_LIMIT",
)

discord_forbidden_session_sleeper = SessionSleep(
    sleep=env.getattr("DISCORD_SESSION_403_SLEEP_INIT"),
    min_sleep=env.getattr("DISCORD_SESSION_403_MIN_SLEEP"),
    difmin=env.getattr("DISCORD_SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("DISCORD_SESSION_403_SLEEP_MAX"),
    decay_threshold=env.getattr("DISCORD_SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("DISCORD_SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("DISCORD_SESSION_403_SLEEP_INCREASE_FACTOR"),
    error_name="DISCORD_SESSION_403",
)

subscription_rate_limit_session_sleeper = SessionSleep(
    sleep=env.getattr("SUBSCRIPTION_SESSION_SLEEP_INIT"),
    min_sleep=env.getattr("SUBSCRIPTION_SESSION_MIN_SLEEP"),
    difmin=env.getattr("SUBSCRIPTION_SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("SUBSCRIPTION_SESSION_SLEEP_MAX"),
    decay_threshold=env.getattr("SUBSCRIPTION_SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("SUBSCRIPTION_SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("SUBSCRIPTION_SESSION_SLEEP_INCREASE_FACTOR"),
    error_name="SUBSCRIPTION_SESSION_RATE_LIMIT",
)

subscription_forbidden_session_sleeper = SessionSleep(
    sleep=env.getattr("SUBSCRIPTION_SESSION_403_SLEEP_INIT"),
    min_sleep=env.getattr("SUBSCRIPTION_SESSION_403_MIN_SLEEP"),
    difmin=env.getattr("SUBSCRIPTION_SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("SUBSCRIPTION_SESSION_403_SLEEP_MAX"),
    decay_threshold=env.getattr("SUBSCRIPTION_SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("SUBSCRIPTION_SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("SUBSCRIPTION_SESSION_403_SLEEP_INCREASE_FACTOR"),
    error_name="SUBSCRIPTION_SESSION_403",
)
