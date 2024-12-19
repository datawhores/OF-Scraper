import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings


def get_max_workers():
    return constants.getattr("MAXFILE_SEMAPHORE") or (settings.get_download_sems())
