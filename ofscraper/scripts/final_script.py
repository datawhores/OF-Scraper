import json
import logging
import subprocess
import os
import traceback

import ofscraper.utils.settings as settings
import ofscraper.managers.manager as manager
from ofscraper.utils.system.subprocess import run
import ofscraper.utils.of_env.of_env as env


def final_script():
    log = logging.getLogger("shared")
    if not settings.get_settings().post_script:
        log.debug("Final script skipped: post_script setting is disabled.")
        return

    script_path = settings.get_settings().post_script
    if not script_path or not os.path.exists(script_path):
        log.error(
            f"Post script path is invalid or not configured: '{script_path}'. Aborting final script."
        )
        return

    log.debug(f"Attempting to run final script: {script_path}")

    try:
        model_manager = manager.Manager.model_manager

        if settings.get_settings().command == "metadata":
            scrape_paid_activity = "scrape_paid_metadata"
        else:
            scrape_paid_activity = "scrape_paid_download"

        # Dynamically build the payload
        payload_data = {
            "like_processed_users": list(model_manager.get_processed("like")),
            "like_unprocessed_users": list(model_manager.get_unprocessed("like")),
            "unlike_processed_users": list(model_manager.get_processed("unlike")),
            "unlike_unprocessed_users": list(model_manager.get_unprocessed("unlike")),
            "download_processed_users": list(model_manager.get_processed("download")),
            "download_unprocessed_users": list(
                model_manager.get_unprocessed("download")
            ),
            # Use the dynamic activity string here
            "scrape_paid_processed_users": list(
                model_manager.get_processed(scrape_paid_activity)
            ),
            "scrape_paid_unprocessed_users": list(
                model_manager.get_unprocessed(scrape_paid_activity)
            ),
        }
        # Dump JSON to a string, no indent for efficiency, ensure_ascii=False for non-ASCII chars
        input_json_str = json.dumps(payload_data, indent=None, ensure_ascii=False)

        run(
            [script_path],
            input=input_json_str,  # Pass the JSON string as stdin
            capture_output=True,  # Capture stdout and stderr
            text=True,  # Decode stdout/stderr as text
            check=True,  # Raise CalledProcessError if script exits with non-zero status
            level=env.getattr("FINAL_SCRIPT_SUBPROCESS_LEVEL"),
            name="Final script",
        )
        log.debug("Final script ran successfully via stdin.")

    # 4. Add comprehensive error handling
    except FileNotFoundError:
        log.error(
            f"Post script executable not found: '{script_path}'. Please ensure the path is correct and the script is executable."
        )
    except subprocess.CalledProcessError as e:
        log.error(f"Post script failed with exit code {e.returncode}: '{script_path}'")
        log.error(f"Post script stdout:\n{e.stdout.strip()}")
        log.error(f"Post script stderr:\n{e.stderr.strip()}")
    except json.JSONDecodeError as e:
        log.error(f"Failed to serialize payload to JSON for final script: {e}")
    except Exception as e:
        log.critical(
            f"An unexpected error occurred while running final script with script '{script_path}': {e}",
            exc_info=True,
        )
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
