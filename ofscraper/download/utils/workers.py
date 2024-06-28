


import ofscraper.utils.config.data as config_data
import ofscraper.utils.constants as constants
def get_max_workers():
    return constants.getattr("MAXFILE_SEMAPHORE") or (config_data.get_download_semaphores()*10)