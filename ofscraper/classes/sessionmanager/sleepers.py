import ofscraper.utils.env.env as env
from ofscraper.classes.sessionmanager.sessionmanager import SessionSleep


rate_limit_session_sleeper = SessionSleep(
    sleep=env.getattr("SESSION_SLEEP_INIT"),
    difmin=env.getattr("SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("SESSION_SLEEP_MAX"),
    decay_threshold=env.getattr("SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("SESSION_SLEEP_INCREASE_FACTOR"),
)

forbidden_session_sleeper = SessionSleep(
    sleep=env.getattr("SESSION_403_SLEEP_INIT"),
    difmin=env.getattr("SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("SESSION_403_SLEEP_MAX"),
    decay_threshold=env.getattr("SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("SESSION_403_SLEEP_INCREASE_FACTOR"),
)


download_rate_limit_session_sleeper = SessionSleep(
    sleep=env.getattr("DOWNLOAD_SESSION_SLEEP_INIT"),
    difmin=env.getattr("DOWNLOAD_SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("DOWNLOAD_SESSION_SLEEP_MAX"),
    decay_threshold=env.getattr("SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("SESSION_SLEEP_INCREASE_FACTOR"),
)

download_forbidden_session_sleeper = SessionSleep(
    sleep=env.getattr("DOWNLOAD_SESSION_403_SLEEP_INIT"),
    difmin=env.getattr("DOWNLOAD_SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("DOWNLOAD_SESSION_403_SLEEP_MAX"),
    decay_threshold=env.getattr("DOWNLOAD_SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("DOWNLOAD_SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("DOWNLOAD_SESSION_403_SLEEP_INCREASE_FACTOR"),
)


cdm_rate_limit_session_sleeper = SessionSleep(
    sleep=env.getattr("CDM_SESSION_SLEEP_INIT"),
    difmin=env.getattr("CDM_SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("CDM_SESSION_SLEEP_MAX"),
    decay_threshold=env.getattr("SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("SESSION_SLEEP_INCREASE_FACTOR"),
)

cdm_forbidden_session_sleeper = SessionSleep(
    sleep=env.getattr("CDM_SESSION_403_SLEEP_INIT"),
    difmin=env.getattr("CDM_SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("CDM_SESSION_403_SLEEP_MAX"),
    decay_threshold=env.getattr("CDM_SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("CDM_SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("CDM_SESSION_403_SLEEP_INCREASE_FACTOR"),
)


like_rate_limit_session_sleeper = SessionSleep(
    sleep=env.getattr("LIKE_SESSION_SLEEP_INIT"),
    difmin=env.getattr("LIKE_SESSION_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("LIKE_SESSION_SLEEP_MAX"),
    decay_threshold=env.getattr("SESSION_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("SESSION_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("SESSION_SLEEP_INCREASE_FACTOR"),
)

like_forbidden_session_sleeper = SessionSleep(
    sleep=env.getattr("LIKE_SESSION_403_SLEEP_INIT"),
    difmin=env.getattr("LIKE_SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
    max_sleep=env.getattr("LIKE_SESSION_403_SLEEP_MAX"),
    decay_threshold=env.getattr("LIKE_SESSION_403_SLEEP_DECAY_THRESHOLD"),
    decay_factor=env.getattr("LIKE_SESSION_403_SLEEP_DECAY_FACTOR"),
    increase_factor=env.getattr("LIKE_SESSION_403_SLEEP_INCREASE_FACTOR"),
)