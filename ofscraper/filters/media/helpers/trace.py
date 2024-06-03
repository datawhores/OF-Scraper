import logging
import ofscraper.utils.constants as constants
from ofscraper.utils.logs.helpers import is_trace


log = logging.getLogger("shared")
def trace_log_media(count, media, filter_str):
    if not is_trace():
        return
    chunk_size = constants.getattr("LARGE_TRACE_CHUNK_SIZE")
    logformater = "{} id: {} postid: {} data: {} "
    for i in range(1, len(media) + 1, chunk_size):
        # Calculate end index considering potential last chunk being smaller
        end_index = min(i + chunk_size - 1, len(media))  # Adjust end_index calculation
        chunk = media[i - 1 : end_index]  # Adjust slice to start at i-1
        log.trace(
            "\n\n\n".join(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> {filter_str} ",
                        x.id,
                        x.postid,
                        x.media,
                    ),
                    chunk,
                )
            )
        )
        # Check if there are more elements remaining after this chunk
        if i + chunk_size > len(media):
            break  # Exit the loop if we've processed all elements


def trace_log_post(count, media, filter_str):
    if not is_trace():
        return
    chunk_size = constants.getattr("LARGE_TRACE_CHUNK_SIZE")
    logformater = "{} id: {} data: {} "
    for i in range(1, len(media) + 1, chunk_size):
        # Calculate end index considering potential last chunk being smaller
        end_index = min(i + chunk_size - 1, len(media))  # Adjust end_index calculation
        chunk = media[i - 1 : end_index]  # Adjust slice to start at i-1
        log.trace(
            "\n\n\n".join(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> {filter_str} ", x.id, x.post
                    ),
                    chunk,
                )
            )
        )
        # Check if there are more elements remaining after this chunk
        if i + chunk_size > len(media):
            break  # Exit the loop if we've processed all elements
