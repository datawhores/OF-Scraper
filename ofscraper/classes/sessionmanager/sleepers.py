import ofscraper.utils.of_env.of_env as env
from ofscraper.classes.sessionmanager.sessionmanager import SessionSleep


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

