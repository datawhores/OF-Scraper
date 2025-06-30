import logging
import subprocess
import os
import traceback
import pathlib
from typing import Union


import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess import run
import ofscraper.utils.of_env.of_env as env


def after_download_script(final_path: Union[str, pathlib.Path]):
    """
    Executes a user-defined script after a download is complete, passing the final file path.

    This function retrieves the path to the user script from the application settings.
    It then invokes this script as a subprocess, passing the `final_path` of the
    downloaded file as a command-line argument.

    Args:
        final_path (str): The absolute path to the downloaded file.
    """
    final_path = str(final_path)
    log = logging.getLogger("shared")
    script_path = settings.get_settings().after_download_script

    if not script_path:
        log.debug("After download script is not configured. Skipping.")
        return

    if not os.path.exists(script_path):
        log.error(
            f"After download script path is invalid: '{script_path}'. Aborting execution."
        )
        return

    log.debug(
        f"Running after download script for '{final_path}' with script: {script_path}"
    )

    try:
        result = run(
            [script_path],  # Pass final_path as a command-line argument
            capture_output=True,
            input=final_path,
            text=True,
            check=True,  # Will raise CalledProcessError for non-zero exit codes
            quiet=True,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if env.getattr("SCRIPT_OUTPUT_SUBPROCCESS"):
            if stdout:
                log.log(
                    100, f"After download script stdout for '{final_path}':\n{stdout}"
                )

            if stderr:
                log.log(
                    100, f"After download script stderr for '{final_path}':\n{stderr}"
                )

        log.info(f"Successfully ran after download script for '{final_path}'.")

    except FileNotFoundError:
        log.error(
            f"After download script executable not found: '{script_path}'. "
            "Please ensure the path is correct and the script has execute permissions."
        )
    except subprocess.CalledProcessError as e:
        log.error(
            f"After download script failed for '{final_path}' with exit code {e.returncode}: '{script_path}'"
        )
        if e.stdout.strip():
            log.error(f"Stdout:\n{e.stdout.strip()}")
        if e.stderr.strip():
            log.error(f"Stderr:\n{e.stderr.strip()}")
    except Exception as e:
        log.critical(
            f"An unexpected error occurred while running after download script for '{final_path}' with script '{script_path}': {e}",
            exc_info=True,
        )
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
