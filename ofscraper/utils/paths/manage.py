import logging
import shutil
import arrow
import traceback
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.console as console_

console=console_.get_shared_console()


def make_folders():
    common_paths.get_config_folder()
    create_profile_path()


def create_profile_path(name=None):
    out = common_paths.get_profile_path(name)
    out.mkdir(exist_ok=True, parents=True)
    return out


def copy_path(source, dst):
    try:
        shutil.copy2(source, dst)
    except OSError as e:
        logging.getLogger("shared").debug("failed to copy with copy2 using copy")
        logging.getLogger("shared").traceback_(e)
        logging.getLogger("shared").traceback_(traceback.format_exc())
        shutil.copy(source, dst)
    except Exception as e:
        raise e


def cleanup_logs():
    """
    Performs actions to cleanup logs
    """
    if not settings.get_settings().logs_expire_time:
        return
    if not settings.get_settings().rotate_logs:
        return
    with stdout.lowstdout():
        delete_old_logs()
        delete_empty_folders()

def delete_old_logs():
    """
    Recursively finds and deletes .log files in the specified folder
    that are older than the given maximum age

    Also cleans up folder
    """
    log_path = common_paths.get_log_folder()
    now = arrow.now().float_timestamp
    for log_file in log_path.rglob("*.log"):  # rglob for recursive globbing
        try:
            if (now - log_file.stat().st_mtime) > settings.get_settings().logs_expire_time*86400000:
                log_file.unlink()  # pathlib's way to delete a file
                console.print(f"Deleted old log file: {log_file}")
        except OSError as e:
            console.print(f"Error deleting file {log_file}: {e}")
def delete_empty_folders():
    """
    Recursively finds and deletes empty folders within thelog folder.

    """
    log_path = common_paths.get_log_folder()

    # Iterate through all directories within the log folder and its subdirectories
    for folder in sorted(log_path.rglob("*"), key=lambda p: len(str(p)), reverse=True):
        if folder.is_dir() and not any(folder.iterdir()):
            try:
                folder.rmdir()
                console.print(f"Deleted empty folder: {folder}")
            except OSError as e:
                console.print(f"Error deleting folder {folder}: {e}")

