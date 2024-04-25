import logging

import ofscraper.utils.constants as constants
from ofscraper.utils.logs.helpers import is_trace

log = logging.getLogger("shared")


def trace_log_user(responseArray, title_str):
    if not is_trace():
        return
    chunk_size = constants.getattr("LARGE_TRACE_CHUNK_SIZE")
    for i in range(1, len(responseArray) + 1, chunk_size):
        # Calculate end index considering potential last chunk being smaller
        end_index = min(
            i + chunk_size - 1, len(responseArray)
        )  # Adjust end_index calculation
        chunk = responseArray[i - 1 : end_index]  # Adjust slice to start at i-1
        log.trace(
            f"{title_str.strip().capitalize()} {{data}}".format(
                data="\n\n".join(list(map(lambda x: f"userdata: {str(x)}", chunk)))
            )
        )
        # Check if there are more elements remaining after this chunk
        if i + chunk_size > len(responseArray):
            break
