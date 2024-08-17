import traceback
import logging
import psutil
import arrow
from ofscraper.utils.system.system import get_all_ofscrapers_processes

DOWNLOAD_OBJ = None


def get_download_speed():
    global DOWNLOAD_OBJ
    if not DOWNLOAD_OBJ:
        pids = list(map(lambda x: x.pid, get_all_ofscrapers_processes()))
        DOWNLOAD_OBJ = MultiProcessDownloadSpeed(pids)
    return DOWNLOAD_OBJ.speed


def add_pids_to_download_obj(pids):
    global DOWNLOAD_OBJ
    if not DOWNLOAD_OBJ:
        named_pids = list(map(lambda x: x.pid, get_all_ofscrapers_processes()))
        DOWNLOAD_OBJ = MultiProcessDownloadSpeed(named_pids)
    DOWNLOAD_OBJ.pids = list(set(DOWNLOAD_OBJ.pids + list(pids)))


class MultiProcessDownloadSpeed:
    """
    This class calculates the total download speed (received bytes per second)
    for a list of processes.

    Args:
        pids: A list of process IDs (pids) to track download information for.
    """

    def __init__(self, pids):
        self._pids = pids
        self.previous_stats = {
            pid: None for pid in pids
        }  # Stores previous stats per pid
        self.previous_time = {pid: None for pid in pids}
        self.previous_speed = {
            pid: 0 for pid in pids
        }  # Stores previous time of measurement
        self._speed = None
        self.previous_run = None

    @property
    def pids(self):
        return self._pids

    @pids.setter
    def pids(self, pids):
        self._pids = pids
        self.previous_stats = {pid: self.previous_stats.get(pid) for pid in pids}
        self.previous_time = {pid: self.previous_time.get(pid) for pid in pids}
        self.previous_speed = {pid: self.previous_speed.get(pid, 0) for pid in pids}

    @property
    def speed(self):
        """
        Calculates and returns the total download speed (received bytes per second)
        for all processes in the pids list.

        Returns:
          The total download speed in bytes per second,
          or None if any process is not found or network info unavailable.
        """
        try:
            # Get current network interface stats

            # Calculate total received bytes since last call
            total_bytes_second = 0
            for pid in self._pids:
                try:
                    if pid is None:
                        continue
                    if not psutil.pid_exists(pid):
                        continue  # Check if process is still running
                    process = psutil.Process(pid)
                    curr_stats = process.io_counters()
                    curr_time = arrow.now().float_timestamp

                    if not self.previous_time.get(pid) or not self.previous_stats.get(
                        pid
                    ):
                        self.previous_stats[pid] = curr_stats
                        self.previous_time[pid] = curr_time
                        continue
                    previous_stats = self.previous_stats[pid]
                    previous_time = self.previous_time[pid]
                    previous_speed = self.previous_speed[pid]
                    if curr_time - previous_time < 1.5:
                        total_bytes_second = total_bytes_second + previous_speed
                    else:
                        self.previous_stats[pid] = curr_stats  # Update previous stats
                        self.previous_time[pid] = curr_time  # Update time stats
                        new_speed = (
                            curr_stats.write_bytes - previous_stats.write_bytes
                        ) / (curr_time - previous_time) or previous_speed
                        total_bytes_second = total_bytes_second + new_speed
                        self.previous_speed[pid] = new_speed

                except Exception as E:
                    logging.getLogger("shared").traceback_(E)
                    logging.getLogger("shared").traceback_(traceback.format_exc())

            return total_bytes_second
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"Error getting download speed: {e}")
            return None
