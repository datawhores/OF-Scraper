import json
import re
import logging
import traceback
import os
import subprocess


import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess import run
import ofscraper.utils.of_env.of_env as env


def skip_download_script(total, ele):
    log = logging.getLogger("shared")

    if not settings.get_settings().skip_download_script:
        log.debug("Download skip script is disabled via settings. Skipping execution.")
        return False

    script_path = settings.get_settings().skip_download_script
    if not script_path or not os.path.exists(script_path):
        log.error(
            f"Download skip script path is invalid or not configured: '{script_path}'. Aborting script execution."
        )
        return False  # Default: Do NOT skip if script path is bad

    try:
        processed_media = ele.media
        processed_post = ele.post.post

        log.debug(
            f"Running download skip script for {ele.username} (media_id: {ele.id}, post_id: {ele.postid})"
        )

        master_dump_payload = {
            "username": ele.username,
            "model_id": ele.model_id,
            "post_id": ele.postid,
            "media_id": ele.id,
            "media": processed_media,
            "post": processed_post,
            "total_size": total,
        }

        input_json_str = json.dumps(
            master_dump_payload, indent=None, ensure_ascii=False
        )

        result = run(
            [script_path],
            input=input_json_str,  # Input must be bytes
            capture_output=True,  # Capture stdout and stderr
            text=True,  # Decode stdout/stderr as text
            check=True,  # Raise CalledProcessError for non-zero exit codes
            quiet=True,
        )

        stdout_output = result.stdout.strip()
        stderr_output = result.stderr.strip()
        if env.getattr("SCRIPT_OUTPUT_SUBPROCCESS"):
            log.log(
                100, f"Download skip script stdout for {ele.username}:\n{stdout_output}"
            )
            if stderr_output:
                log.log(
                    100,
                    f"Download skip script stderr for {ele.username}:\n{stderr_output}",
                )
        should_skip = (stdout_output.lower() == "false") or (stdout_output == "")
        if should_skip:
            log.debug(
                f"Download skip script instructed to SKIP download for {ele.username} (media_id: {ele.id})."
            )
        else:
            log.debug(
                f"Download skip script instructed to PROCEED with download for {ele.username} (media_id: {ele.id})."
            )

        return should_skip  # Return True if skipped, False if proceeds

    except FileNotFoundError:
        log.error(
            f"Download skip script executable not found: '{script_path}'. Please ensure the path is correct and the script is executable."
        )
        return False  # Default: Do NOT skip on error
    except subprocess.CalledProcessError as e:
        log.error(
            f"Download skip script failed for {ele.username} with exit code {e.returncode}: '{script_path}'"
        )
        log.error(f"Download skip script stdout:\n{e.stdout.strip()}")
        log.error(f"Download skip script stderr:\n{e.stderr.strip()}")
        return False  # Default: Do NOT skip on error
    except json.JSONDecodeError as e:
        log.error(
            f"Failed to serialize payload to JSON for download skip script for {ele.username}: {e}"
        )
        return False  # Default: Do NOT skip on error
    except Exception as e:
        log.critical(
            f"An unexpected error occurred while running download skip script for {ele.username} with script '{script_path}': {e}",
            exc_info=True,
        )
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
        return False  # Default: Do NOT skip on error
