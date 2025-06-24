import ofscraper.utils.env.env as env
import ofscraper.utils.settings as settings


def get_max_workers():
    return env.getattr("MAXFILE_SEMAPHORE") or (
        settings.get_settings().download_sems
    )
