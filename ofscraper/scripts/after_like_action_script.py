import json
import logging
import traceback
import os  # For checking script path existence
import subprocess


import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess import run
import ofscraper.managers.manager as manager
import ofscraper.utils.of_env.of_env as env


def after_like_action_script(username, media, posts=None, action=None):
    log = logging.getLogger("shared")
    action = action or "like"
    if not settings.get_settings().after_action_script:
        return
    script_path = settings.get_settings().after_action_script
    if not script_path or not os.path.exists(script_path):
        log.error(
            f"After like action script path is invalid or not configured: '{script_path}'. Aborting after like action script."
        )
        return

    userdata = manager.Manager.model_manager.get_model(username)
    if not userdata:
        log.warning(
            f"Could not retrieve user data for {username}. Aborting after like action script."
        )
        return
    if not posts:
        posts = list({ele.post.id: ele.post for ele in media}.values())
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
            "action": action,
            "model_id": model_id,
            "media": processed_media,
            "posts": processed_posts,
            "userdata": userdict_data,
        }

        input_json_str = json.dumps(
            master_dump_payload, indent=None, ensure_ascii=False
        )

        run(
            [script_path],
            input=input_json_str,  # Pass the JSON string as stdin
            capture_output=True,  # Capture stdout and stderr
            text=True,  # Decode stdout/stderr as text
            check=True,  # Raise CalledProcessError if script exits with non-zero status
            name="after like action script",
            level=env.getattr("AFTER_LIKE_ACTION_SCRIPT_SUBPROCESS_LEVEL"),
        )
        log.debug(
            f"After like action script ran successfully for {processed_username} via stdin."
        )

    except FileNotFoundError:
        log.error(
            f"After like action script executable not found: '{script_path}'. Please ensure the path is correct and the script is executable."
        )
    except subprocess.CalledProcessError as e:
        log.error(
            f"After like action script failed for {processed_username} with exit code {e.returncode}: '{script_path}'"
        )
        log.error(f"After like action script stdout:\n{e.stdout.strip()}")
        log.error(f"After like action script stderr:\n{e.stderr.strip()}")
    except json.JSONDecodeError as e:
        log.error(
            f"Failed to serialize payload to JSON for after like action script for {processed_username}: {e}"
        )
    except Exception as e:
        log.critical(
            f"An unexpected error occurred while running after like script for {processed_username} with script '{script_path}': {e}",
            exc_info=True,
        )
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
