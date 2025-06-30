import json
import logging
import traceback
import os  # For checking script path existence
import subprocess


import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess import run
import ofscraper.main.manager as manager
import ofscraper.utils.of_env.of_env as env


def after_download_action_script(username, media=None, posts=None,action=None):
    log = logging.getLogger("shared")
    action=action or "download"
    if not settings.get_settings().after_action_script:
        return
    script_path = settings.get_settings().after_action_script
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
    if not posts and media:
        posts = list({media.post.id: media.post for ele in media}.values())
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
            "action":"download",
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
            input=input_json_str,  # Pass the JSON string as stdin
            capture_output=True,  # Capture stdout and stderr
            text=True,  # Decode stdout/stderr as text
            check=True,  # Raise CalledProcessError if script exits with non-zero status
            quiet=True,
        )
        if env.getattr("SCRIPT_OUTPUT_SUBPROCCESS"):
            log.log(
                100,
                f"Post user script stdout for {processed_username}:\n{result.stdout.strip()}",
            )
            if result.stderr:
                log.warning(
                    100,
                    f"Post user script stderr for {processed_username}:\n{result.stderr.strip()}",
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
