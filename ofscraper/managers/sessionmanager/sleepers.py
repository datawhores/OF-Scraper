import ofscraper.utils.of_env.of_env as env
from ofscraper.managers.sessionmanager.sessionmanager import SessionSleep

class Sleeper:
    """
    Manages the creation of SessionSleep instances, creating them on-demand
    to ensure they use the most current environment settings.
    """
    def __init__(self):
        """
        Initializes all sleeper instances to None. They will be created
        on first access.
        """
        self._rate_limit = None
        self._forbidden = None
        self._download_rate_limit = None
        self._download_forbidden = None
        self._cdm_rate_limit = None
        self._cdm_forbidden = None
        self._like_rate_limit = None
        self._like_forbidden = None
        self._metadata_rate_limit = None
        self._metadata_forbidden = None
        self._discord_rate_limit = None
        self._discord_forbidden = None
        self._subscription_rate_limit = None
        self._subscription_forbidden = None

    def _create_sleeper(self, prefix: str, error_name: str) -> SessionSleep:
        """A helper factory to create a SessionSleep instance."""
        return SessionSleep(
            sleep=env.getattr(f"{prefix}_SLEEP_INIT"),
            min_sleep=env.getattr(f"{prefix}_MIN_SLEEP"),
            difmin=env.getattr(f"{prefix}_SLEEP_INCREASE_TIME_DIFF"),
            max_sleep=env.getattr(f"{prefix}_SLEEP_MAX"),
            decay_threshold=env.getattr(f"{prefix}_DECAY_THRESHOLD"),
            decay_factor=env.getattr(f"{prefix}_DECAY_FACTOR"),
            increase_factor=env.getattr(f"{prefix}_SLEEP_INCREASE_FACTOR"),
            error_name=error_name,
        )

    @property
    def rate_limit_session_sleeper(self) -> SessionSleep:
        if self._rate_limit is None:
            self._rate_limit = self._create_sleeper("SESSION", "SESSION_RATE_LIMIT")
        return self._rate_limit

    @property
    def forbidden_session_sleeper(self) -> SessionSleep:
        if self._forbidden is None:
            self._forbidden = self._create_sleeper("SESSION_403", "SESSION_403")
        return self._forbidden

    @property
    def download_rate_limit_session_sleeper(self) -> SessionSleep:
        if self._download_rate_limit is None:
            self._download_rate_limit = self._create_sleeper("DOWNLOAD_SESSION", "DOWNLOAD_SESSION_RATE_LIMIT")
        return self._download_rate_limit

    @property
    def download_forbidden_session_sleeper(self) -> SessionSleep:
        if self._download_forbidden is None:
            self._download_forbidden = self._create_sleeper("DOWNLOAD_SESSION_403", "DOWNLOAD_SESSION_403")
        return self._download_forbidden

    @property
    def cdm_rate_limit_session_sleeper(self) -> SessionSleep:
        if self._cdm_rate_limit is None:
            self._cdm_rate_limit = self._create_sleeper("CDM_SESSION", "CDM_SESSION_RATE_LIMIT")
        return self._cdm_rate_limit

    @property
    def cdm_forbidden_session_sleeper(self) -> SessionSleep:
        if self._cdm_forbidden is None:
            self._cdm_forbidden = self._create_sleeper("CDM_SESSION_403", "CDM_SESSION_403")
        return self._cdm_forbidden

    @property
    def like_rate_limit_session_sleeper(self) -> SessionSleep:
        if self._like_rate_limit is None:
            self._like_rate_limit = self._create_sleeper("LIKE_SESSION", "LIKE_SESSION_RATE_LIMIT")
        return self._like_rate_limit

    @property
    def like_forbidden_session_sleeper(self) -> SessionSleep:
        if self._like_forbidden is None:
            self._like_forbidden = self._create_sleeper("LIKE_SESSION_403", "LIKE_SESSION_403")
        return self._like_forbidden

    @property
    def metadata_rate_limit_session_sleeper(self) -> SessionSleep:
        if self._metadata_rate_limit is None:
            self._metadata_rate_limit = self._create_sleeper("METADATA_SESSION", "METADATA_SESSION_RATE_LIMIT")
        return self._metadata_rate_limit

    @property
    def metadata_forbidden_session_sleeper(self) -> SessionSleep:
        if self._metadata_forbidden is None:
            self._metadata_forbidden = self._create_sleeper("METADATA_SESSION_403", "METADATA_SESSION_403")
        return self._metadata_forbidden

    @property
    def discord_rate_limit_session_sleeper(self) -> SessionSleep:
        if self._discord_rate_limit is None:
            self._discord_rate_limit = self._create_sleeper("DISCORD_SESSION", "DISCORD_SESSION_RATE_LIMIT")
        return self._discord_rate_limit

    @property
    def discord_forbidden_session_sleeper(self) -> SessionSleep:
        if self._discord_forbidden is None:
            self._discord_forbidden = self._create_sleeper("DISCORD_SESSION_403", "DISCORD_SESSION_403")
        return self._discord_forbidden

    @property
    def subscription_rate_limit_session_sleeper(self) -> SessionSleep:
        if self._subscription_rate_limit is None:
            self._subscription_rate_limit = self._create_sleeper("SUBSCRIPTION_SESSION", "SUBSCRIPTION_SESSION_RATE_LIMIT")
        return self._subscription_rate_limit

    @property
    def subscription_forbidden_session_sleeper(self) -> SessionSleep:
        if self._subscription_forbidden is None:
            self._subscription_forbidden = self._create_sleeper("SUBSCRIPTION_SESSION_403", "SUBSCRIPTION_SESSION_403")
        return self._subscription_forbidden

# Create a single, global instance of the manager that can be imported elsewhere
sleepers = Sleeper()
