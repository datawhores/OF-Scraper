import logging
import json
import subprocess
import traceback
import arrow
import ofscraper.utils.settings as settings
import ofscraper.utils.config.data as config_data
from ofscraper.utils.system.subprocess import run
import ofscraper.utils.of_env.of_env as env
from ofscraper.classes.of.posts import Post
from ofscraper.classes.of.media import Media


def naming_script(dir, file, ele):
    log = logging.getLogger("shared")

    if not settings.get_settings().naming_script:
        return

    script_path = settings.get_settings().naming_script
    if not script_path:
        log.error("Naming script path is not configured. Aborting naming script.")
        return

    log.debug(f"Attempting to run naming script: {script_path}")

    try:
        payload_data = {
            "dir": str(dir),
            "file": str(file),
            "dir_format": config_data.get_dirformat(),
            "file_format": config_data.get_fileformat(),
            "metadata": config_data.get_metadata(),
            "username": ele.username,
            "model_id": ele.model_id,
            "value": ele.value.capitalize(),
            "response_type": ele.modified_responsetype,
            "label": ele.label_string,
        }

        if isinstance(ele, Media):
            payload_data.update(
                {
                    "media": ele.media,
                    "post": ele.post.post,
                    "post_id": ele.post_id,
                    "media_id": ele.id,
                    "media_type": ele.mediatype.capitalize(),
                    "date": arrow.get(ele.postdate).format(config_data.get_date()),
                    "download_type": ele.downloadtype,
                }
            )
        elif isinstance(ele, Post):
            payload_data.update(
                {
                    "media": None,
                    "post": ele.post,
                    "post_id": ele.id,
                    "media_id": None,
                    "media_type": None,
                    "date": arrow.get(ele.date).format(config_data.get_date()),
                    "download_type": None,
                }
            )
        else:
            # Optional: Handle cases where 'ele' is an unexpected type.
            log.error(f"Unsupported type for naming script: {type(ele)}")
            return

        input_json_str = json.dumps(payload_data, indent=None, ensure_ascii=False)

        result = run(
            [script_path],
            input=input_json_str,  # Pass the JSON string as stdin
            capture_output=True,
            text=True,  # Decode stdout/stderr as text
            check=True,  # Raise CalledProcessError for non-zero exit codes
            level=env.getattr("NAMING_SCRIPT_SUBPROCESS_LEVEL"),
            name="naming script",
        )
        log.debug("Naming script ran successfully via stdin.")
        return result.stdout.strip()

    except FileNotFoundError:
        log.error(
            f"Naming script executable not found: '{script_path}'. Please ensure the path is correct and the script is executable."
        )
    except subprocess.CalledProcessError as e:
        log.error(
            f"Naming script failed with exit code {e.returncode}: '{script_path}'"
        )
        log.error(f"Naming script stdout:\n{e.stdout.strip()}")
        log.error(f"Naming script stderr:\n{e.stderr.strip()}")
    except json.JSONDecodeError as e:
        log.error(f"Failed to serialize payload to JSON for naming script: {e}")
    except Exception as e:
        log.critical(
            f"An unexpected error occurred while running naming script '{script_path}': {e}",
            exc_info=True,
        )
        log.critical(
            f"An unexpected error occurred while running final script with script '{script_path}': {e}",
            exc_info=True,
        )
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
