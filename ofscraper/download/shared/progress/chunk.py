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
    available_memory = (
        psutil.virtual_memory().available - 1024 * 1024 * 512
    )  # Reserve 512MB buffer

    # Target a chunk size that utilizes a reasonable portion of available memory
    max_chunk_size = min(
        available_memory //constants.getattr("CHUNK_MEMORY_SPLIT") , constants.getattr("MAX_CHUNK_SIZE")
    )  # Max 10MB
    # Adjust chunk size based on file size (consider smaller sizes for larger files, with minimum)
    ideal_chunk_size = min(max_chunk_size, file_size //constants.getattr("CHUNK_FILE_SPLIT"))
    ideal_chunk_size = max(
        ideal_chunk_size -(ideal_chunk_size%4096),
        constants.getattr("MIN_CHUNK_SIZE"),
    )  # Minimum 4KB chunk
    return ideal_chunk_size


def get_update_count(total_size, curr_file, chunk_size):
    curr_file_size = (
        pathlib.Path(curr_file).absolute().stat().st_size
        if pathlib.Path(curr_file).exists()
        else 0
    )
    file_size = total_size - curr_file_size

    return max((file_size // chunk_size) // constants.getattr("CHUNK_UPDATE_COUNT"), 1)