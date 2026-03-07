import json
import re
import logging
import traceback
import os
import subprocess

import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess import async_run 
import ofscraper.utils.of_env.of_env as env


async def skip_download_script(total, ele): # Made async
    log = logging.getLogger("shared")

    if not settings.get_settings().skip_download_script:
        log.info("Download skip script is disabled via settings. Skipping execution.")
        return False

    script_path = settings.get_settings().skip_download_script
    if not script_path or not os.path.exists(script_path):
        log.info(
            f"Download skip script path is invalid or not configured: '{script_path}'. Aborting script execution."
        )
        return False

    try:
        processed_media = ele.media
        processed_post = ele.post.post

        log.info(
            f"Running download skip script for {ele.username} (media_id: {ele.id}, post_id: {ele.post_id})"
        )

        master_dump_payload = {
            "username": ele.username,
            "model_id": ele.model_id,
            "post_id": ele.post_id,
            "media_id": ele.id,
            "media": processed_media,
            "post": processed_post,
            "total_size": total,
        }

        input_json_str = json.dumps(
            master_dump_payload, indent=None, ensure_ascii=False
        )

        # Await the new async runner
        result = await async_run(
            [script_path],
            input=input_json_str, 
            capture_output=True,  
            text=True,  
            check=True,  
            level=env.getattr("SKIP_DOWNLOAD_SCRIPT_SUBPROCESS_LEVEL"),
            name="skip download script",
        )

        stdout_output = result.stdout.strip()
        stderr_output = result.stderr.strip()
        if env.getattr("SCRIPT_OUTPUT_SUBPROCCESS"):
            log.log(
                env.getattr("SCRIPT_OUTPUT_SUBPROCCESS_LEVEL"),
                f"Download skip script stdout for {ele.username}:\n{stdout_output}",
            )
            if stderr_output:
                log.log(
                    env.getattr("SCRIPT_OUTPUT_SUBPROCCESS_LEVEL"),
                    f"Download skip script stderr for {ele.username}:\n{stderr_output}",
                )
        should_skip = (stdout_output.lower() == "false") or (stdout_output == "")
        if should_skip:
            log.info(f"Download skip script instructed to SKIP download for {ele.username} (media_id: {ele.id}).")
        else:
            log.info(f"Download skip script instructed to PROCEED with download for {ele.username} (media_id: {ele.id}).")

        return should_skip 

    except FileNotFoundError:
        log.info(f"Download skip script executable not found: '{script_path}'.")
        return False 
    except subprocess.CalledProcessError as e:
        log.info(f"Download skip script failed for {ele.username} with exit code {e.returncode}: '{script_path}'")
        if e.stdout and e.stdout.strip(): log.debug(f"Stdout:\n{e.stdout.strip()}")
        if e.stderr and e.stderr.strip(): log.debug(f"Stderr:\n{e.stderr.strip()}")
        return False
    except json.JSONDecodeError as e:
        log.info(f"Failed to serialize payload to JSON for download skip script for {ele.username}: {e}")
        return False
    except Exception as e:
        log.info(f"An unexpected error occurred while running download skip script for {ele.username} with script '{script_path}': {e}", exc_info=True)
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
        return False