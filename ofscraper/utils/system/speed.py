import os
import psutil
import arrow
import logging
import traceback

# Global state for the single process
_previous_stats = None
_previous_time = None
_previous_speed = 0


def get_download_speed():
    """
    Calculates the disk write speed (bytes per second) of the current process.
    """
    global _previous_stats, _previous_time, _previous_speed
    try:
        # Only check the current process
        process = psutil.Process(os.getpid())
        curr_stats = process.io_counters()
        curr_time = arrow.now().float_timestamp

        # Initialize on first run
        if not _previous_time or not _previous_stats:
            _previous_stats = curr_stats
            _previous_time = curr_time
            return 0

        # Return cached speed if less than 1.5 seconds have passed (prevents CPU spam)
        if curr_time - _previous_time < 1.5:
            return _previous_speed

        # Calculate new speed
        bytes_written = curr_stats.write_bytes - _previous_stats.write_bytes
        time_elapsed = curr_time - _previous_time
        new_speed = (
            bytes_written / time_elapsed if time_elapsed > 0 else _previous_speed
        )

        # Update cache
        _previous_stats = curr_stats
        _previous_time = curr_time
        _previous_speed = new_speed

        return new_speed

    except Exception as E:
        logging.getLogger("shared").traceback_(E)
        logging.getLogger("shared").traceback_(traceback.format_exc())
        return 0
