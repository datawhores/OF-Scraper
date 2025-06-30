import json
import re
import logging
import traceback
import tempfile


import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess import run
import ofscraper.main.manager as manager

import logging
import json
import subprocess
import traceback  # Keep this for detailed traceback if needed by log.traceback_
import sys  # For printing warnings/errors to stderr
import os  # For checking script path existence

# Assuming these are accessible from your modules (adjust import paths as needed)
# import ofscraper.utils.config.settings as settings
# import ofscraper.classes.manager as manager


def post_user_script(username, media=None, posts=None):
    log = logging.getLogger("shared")
    if not settings.get_settings().download_script:
        return
    script_path = settings.get_settings().download_script
    if not script_path or not os.path.exists(script_path):
        log.error(
            f"Download script path is invalid or not configured: '{script_path}'. Aborting post user script."
        )
        return

    userdata = manager.Manager.model_manager.get_model(username)
    if not userdata:
        log.warning(
            f"Could not retrieve user data for {username}. Aborting post user script."
        )
        return

    try:
        processed_username = (
            userdata["username"] if isinstance(userdata, dict) else userdata.name
        )
        model_id = userdata["id"] if isinstance(userdata, dict) else userdata.id
        userdict_data = (
            userdata
            if isinstance(userdata, dict)
            else (userdata.model if hasattr(userdata, "model") else None)
        )
        log.debug(
            f"Running post user script for {processed_username} with script: {script_path}"
        )

        processed_posts = [x.post for x in (posts or [])]
        processed_media = [x.media for x in (media or [])]

        master_dump_payload = {
            "username": processed_username,
            "model_id": model_id,
            "media": processed_media,
            "posts": processed_posts,
            "userdata": userdict_data,
        }

        input_json_str = json.dumps(
            master_dump_payload, indent=None, ensure_ascii=False
        )

        result = run(
            [script_path],
            input=input_json_str.encode(
                "utf-8"
            ),  # Pass the JSON string as stdin (run converts to utf-8 str in text mode)
            capture_output=True,  # Capture stdout and stderr
            text=True,  # Decode stdout/stderr as text (requires input as str)
            check=True,  # Raise CalledProcessError if script exits with non-zero status
        )

        log.debug(
            f"Post user script stdout for {processed_username}:\n{result.stdout.strip()}"
        )
        if result.stderr:
            log.warning(
                f"Post user script stderr for {processed_username}:\n{result.stderr.strip()}"
            )
        log.debug(
            f"Post user script ran successfully for {processed_username} via stdin."
        )

    except FileNotFoundError:
        log.error(
            f"Post user script executable not found: '{script_path}'. Please ensure the path is correct and the script is executable."
        )
    except subprocess.CalledProcessError as e:
        log.error(
            f"Post user script failed for {processed_username} with exit code {e.returncode}: '{script_path}'"
        )
        log.error(f"Post user script stdout:\n{e.stdout.strip()}")
        log.error(f"Post user script stderr:\n{e.stderr.strip()}")
    except json.JSONDecodeError as e:
        log.error(
            f"Failed to serialize payload to JSON for post user script for {processed_username}: {e}"
        )
    except Exception as e:
        log.critical(
            f"An unexpected error occurred while running post user script for {processed_username} with script '{script_path}': {e}",
            exc_info=True,
        )
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
