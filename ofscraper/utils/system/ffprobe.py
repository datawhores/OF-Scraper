import subprocess
import logging

log = logging.getLogger("shared")

def get_video_duration(file_path):
    """Uses ffprobe to get the actual duration of the downloaded video in seconds."""
    try:
        cmd = [
            'ffprobe', 
            '-v', 'error', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        log.debug(f"ffprobe could not read duration for {file_path}: {e}")
        return None

def verify_media_integrity(file_path, expected_duration_seconds):
    """Returns True if the video is healthy and matches the expected length."""
    actual_duration = get_video_duration(file_path)
    
    # If ffprobe fails completely, the file is totally corrupted
    if actual_duration is None:
        return False
        
    # If the duration is more than 2% shorter than expected, it's truncated
    if expected_duration_seconds:
        ratio = actual_duration / expected_duration_seconds
        if ratio < 0.98:
            log.warning(f"Video truncated! Expected: {expected_duration_seconds}s, Actual: {actual_duration}s")
            return False
            
    return True