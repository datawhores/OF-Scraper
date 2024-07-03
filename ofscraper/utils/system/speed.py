import psutil
import time
from ofscraper.utils.system.system import get_all_ofscrapers_processes

DOWNLOAD_OBJ=None
def get_download_speed():
    global DOWNLOAD_OBJ
    if not DOWNLOAD_OBJ:
        pids=list(map(lambda x:x.pid,get_all_ofscrapers_processes()))
        DOWNLOAD_OBJ=MultiProcessDownloadSpeed(pids)
    return DOWNLOAD_OBJ.get_download_speed()


class MultiProcessDownloadSpeed:
  """
  This class calculates the total download speed (received bytes per second) 
  for a list of processes.

  Args:
      pids: A list of process IDs (pids) to track download information for.
  """
  def __init__(self, pids):
    self.pids = pids
    self.previous_stats = {pid: None for pid in pids}  # Stores previous stats per pid
    self.previous_time = None   # Stores previous time of measurement

  def get_download_speed(self):
    """
    Calculates and returns the total download speed (received bytes per second) 
    for all processes in the pids list.

    Returns:
      The total download speed in bytes per second, 
      or None if any process is not found or network info unavailable.
    """
    try:
      # Get current network interface stats
      current_stats = psutil.net_io_counters()
      current_time = time.time()
      
      # Check if this is the first call (no previous stats)
      if self.previous_time is None:
        self.previous_stats = {pid: current_stats for pid in self.pids}
        self.previous_time = current_time
        return 0

      # Calculate time difference
      time_delta = current_time - self.previous_time

      # Calculate total received bytes since last call
      total_received_bytes = 0
      for pid in self.pids:
            try:
                if pid in current_stats:  # Check if process is still running
                    previous_stats = self.previous_stats[pid]
                    total_received_bytes += current_stats.bytes_recv - previous_stats.bytes_recv
                    self.previous_stats[pid] = current_stats  # Update previous stats
                else:
                    print(f"Process {pid} not found. Removing from list.")
                    self.pids.remove(pid)
                    if not self.pids:  # No processes left, stop tracking
                        return None
            except Exception as E:
               print(E)

      # Update previous time for next call
      self.previous_time = current_time

      # Calculate total download speed in bytes per second
      total_download_speed = total_received_bytes / time_delta

      return total_download_speed
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
      print(f"Error getting download speed: {e}")
      return None