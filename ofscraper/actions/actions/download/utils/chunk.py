r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import pathlib

import psutil
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings


AVALIBLE_MEMORY = None


def get_available_memory():
    global AVALIBLE_MEMORY
    if not AVALIBLE_MEMORY:
        AVALIBLE_MEMORY = psutil.virtual_memory().available - 1024 * 1024
    return AVALIBLE_MEMORY


def get_ideal_chunk_size(total_size, curr_file):
    """
    Suggests a chunk size based on file size and a calculated available memory buffer.

    Args:
        file_size (int): Size of the file being downloaded in bytes.

    Returns:
        int: Suggested chunk size in bytes.
    """
    curr_file_size = (
        pathlib.Path(curr_file).absolute().stat().st_size
        if pathlib.Path(curr_file).exists()
        else 0
    )
    file_size = total_size - curr_file_size

    # Estimate available memory (considering a buffer for system operations)

    available_memory = get_available_memory()
    # Target a chunk size that utilizes a reasonable portion of available memory
    max_chunk_size = min(
        available_memory // constants.getattr("CHUNK_MEMORY_SPLIT"),
        constants.getattr("MAX_CHUNK_SIZE"),
    )
    ideal_chunk_size = max(
        min(max_chunk_size, file_size // constants.getattr("CHUNK_FILE_SPLIT")),
        constants.getattr("MIN_CHUNK_SIZE"),
    )
    if settings.get_download_limit()==0:
        pass
    elif ideal_chunk_size // 16 > settings.get_download_limit() or float("inf"):
        ideal_chunk_size = settings.get_download_limit()
    ideal_chunk_size = ideal_chunk_size - (ideal_chunk_size % 1024)
    return ideal_chunk_size


def get_update_count(total_size, curr_file, chunk_size):
    curr_file_size = (
        pathlib.Path(curr_file).absolute().stat().st_size
        if pathlib.Path(curr_file).exists()
        else 0
    )
    file_size = total_size - curr_file_size

    return max((file_size // chunk_size) // constants.getattr("CHUNK_UPDATE_COUNT"), 1)
