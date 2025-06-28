import ofscraper.utils.of_env.of_env as of_env
from ofscraper.classes.sessionmanager.sessionmanager import SessionSleep


rate_limit_session_sleeper = SessionSleep(
    sleep=of_env.getattr("SESSION_SLEEP_INIT"),
    difmin=of_env.getattr("SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=of_env.getattr("SESSION_SLEEP_MAX"),
    decay_threshold=of_env.getattr("SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=of_env.getattr("SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=of_env.getattr("SESSION_SLEEP_INCREASE_FACTOR"),
)

forbidden_session_sleeper = SessionSleep(
    sleep=of_env.getattr("SESSION_403_SLEEP_INIT"),
    difmin=of_env.getattr("SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=of_env.getattr("SESSION_403_SLEEP_MAX"),
    decay_threshold=of_env.getattr("SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=of_env.getattr("SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=of_env.getattr("SESSION_403_SLEEP_INCREASE_FACTOR"),
)


download_rate_limit_session_sleeper = SessionSleep(
    sleep=of_env.getattr("DOWNLOAD_SESSION_SLEEP_INIT"),
    difmin=of_env.getattr("DOWNLOAD_SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=of_env.getattr("DOWNLOAD_SESSION_SLEEP_MAX"),
    decay_threshold=of_env.getattr("SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=of_env.getattr("SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=of_env.getattr("SESSION_SLEEP_INCREASE_FACTOR"),
)

download_forbidden_session_sleeper = SessionSleep(
    sleep=of_env.getattr("DOWNLOAD_SESSION_403_SLEEP_INIT"),
    difmin=of_env.getattr("DOWNLOAD_SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=of_env.getattr("DOWNLOAD_SESSION_403_SLEEP_MAX"),
    decay_threshold=of_env.getattr("DOWNLOAD_SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=of_env.getattr("DOWNLOAD_SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=of_env.getattr("DOWNLOAD_SESSION_403_SLEEP_INCREASE_FACTOR"),
)


cdm_rate_limit_session_sleeper = SessionSleep(
    sleep=of_env.getattr("CDM_SESSION_SLEEP_INIT"),
    difmin=of_env.getattr("CDM_SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=of_env.getattr("CDM_SESSION_SLEEP_MAX"),
    decay_threshold=of_env.getattr("SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=of_env.getattr("SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=of_env.getattr("SESSION_SLEEP_INCREASE_FACTOR"),
)

cdm_forbidden_session_sleeper = SessionSleep(
    sleep=of_env.getattr("CDM_SESSION_403_SLEEP_INIT"),
    difmin=of_env.getattr("CDM_SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=of_env.getattr("CDM_SESSION_403_SLEEP_MAX"),
    decay_threshold=of_env.getattr("CDM_SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=of_env.getattr("CDM_SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=of_env.getattr("CDM_SESSION_403_SLEEP_INCREASE_FACTOR"),
)


like_rate_limit_session_sleeper = SessionSleep(
    sleep=of_env.getattr("LIKE_SESSION_SLEEP_INIT"),
    difmin=of_env.getattr("LIKE_SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=of_env.getattr("LIKE_SESSION_SLEEP_MAX"),
    decay_threshold=of_env.getattr("SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=of_env.getattr("SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=of_env.getattr("SESSION_SLEEP_INCREASE_FACTOR"),
)

like_forbidden_session_sleeper = SessionSleep(
    sleep=of_env.getattr("LIKE_SESSION_403_SLEEP_INIT"),
    difmin=of_env.getattr("LIKE_SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=of_env.getattr("LIKE_SESSION_403_SLEEP_MAX"),
    decay_threshold=of_env.getattr("LIKE_SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=of_env.getattr("LIKE_SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=of_env.getattr("LIKE_SESSION_403_SLEEP_INCREASE_FACTOR"),
)
