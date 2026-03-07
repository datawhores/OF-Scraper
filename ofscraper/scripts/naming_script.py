import logging
import json
import os
import subprocess
import traceback
import arrow
import ofscraper.utils.settings as settings
import ofscraper.utils.config.data as config_data
from ofscraper.utils.system.subprocess import async_run # Changed to async_run
import ofscraper.utils.of_env.of_env as env
from ofscraper.classes.of.posts import Post
from ofscraper.classes.of.media import Media


async def naming_script(dir, file, ele): # Made async
    log = logging.getLogger("shared")

    if not settings.get_settings().naming_script:
        return

    script_path = settings.get_settings().naming_script
    if not script_path or not os.path.exists(script_path):
        log.info(
            f"naming script path is invalid or not configured: '{script_path}'. Aborting final script."
        )
        return

    log.info(f"Attempting to run naming script: {script_path}")

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
            log.info(f"Unsupported type for naming script: {type(ele)}")
            return

        input_json_str = json.dumps(payload_data, indent=None, ensure_ascii=False)

        # Await the new async runner
        result = await async_run(
            [script_path],
            input=input_json_str,  
            capture_output=True,
            text=True,  
            check=True,  
            level=env.getattr("NAMING_SCRIPT_SUBPROCESS_LEVEL"),
            name="naming script",
        )
        log.info("Naming script ran successfully via stdin.")
        return result.stdout.strip() if result and result.stdout else None

    except FileNotFoundError:
        log.info(f"Naming script executable not found: '{script_path}'.")
    except subprocess.CalledProcessError as e:
        log.info(f"Naming script failed with exit code {e.returncode}: '{script_path}'")
        if e.stdout and e.stdout.strip(): log.debug(f"Stdout:\n{e.stdout.strip()}")
        if e.stderr and e.stderr.strip(): log.debug(f"Stderr:\n{e.stderr.strip()}")
    except json.JSONDecodeError as e:
        log.info(f"Failed to serialize payload to JSON for naming script: {e}")
    except Exception as e:
        log.info(f"An unexpected error occurred while running naming script '{script_path}': {e}", exc_info=True)
        log.traceback_(e)
        log.traceback_(traceback.format_exc())