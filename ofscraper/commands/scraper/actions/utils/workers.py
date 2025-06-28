import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings


def get_max_workers():
    return of_env.getattr("MAXFILE_SEMAPHORE") or (
        settings.get_settings().download_sems
    )
