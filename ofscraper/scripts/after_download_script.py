import logging
import subprocess
import os
import traceback
import pathlib
from typing import Union

import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess import async_run
import ofscraper.utils.of_env.of_env as env


async def after_download_script(final_path: Union[str, pathlib.Path]): 
    final_path = str(final_path)
    log = logging.getLogger("shared")
    script_path = settings.get_settings().after_download_script

    if not script_path:
        log.debug("After download script is not configured. Skipping.")
        return

    if not os.path.exists(script_path):
        log.info(
            f"After download script path is invalid: '{script_path}'. Aborting execution."
        )
        return

    log.info(
        f"Running after download script for '{final_path}' with script: {script_path}"
    )

    try:
        # Run the script asynchronously and capture the output
        result = await async_run(
            [script_path],  
            capture_output=True,
            input=final_path,  # Pipe the file path into stdin
            text=True,
            check=True,  
            level=env.getattr("AFTER_DOWNLOAD_SCRIPT_SUBPROCESS_LEVEL"),
            name="after download script",
            timeout=600 
        )

        # --- Explicitly log stdout/stderr mirroring other scripts ---
        if result:
            stdout_output = result.stdout.strip() if result.stdout else ""
            stderr_output = result.stderr.strip() if result.stderr else ""
            
            if env.getattr("SCRIPT_OUTPUT_SUBPROCCESS"):
                if stdout_output:
                    log.log(
                        env.getattr("SCRIPT_OUTPUT_SUBPROCCESS_LEVEL"),
                        f"After download script stdout for '{final_path}':\n{stdout_output}",
                    )
                if stderr_output:
                    log.log(
                        env.getattr("SCRIPT_OUTPUT_SUBPROCCESS_LEVEL"),
                        f"After download script stderr for '{final_path}':\n{stderr_output}",
                    )

        log.info(f"Successfully ran after download script for '{final_path}'.")

    except FileNotFoundError:
        log.info(f"After download script executable not found: '{script_path}'. Please ensure the path is correct and the script has execute permissions.")
    except subprocess.CalledProcessError as e:
        log.info(f"After download script failed for '{final_path}' with exit code {e.returncode}: '{script_path}'")
        if e.stdout and e.stdout.strip(): log.debug(f"Stdout:\n{e.stdout.strip()}")
        if e.stderr and e.stderr.strip(): log.debug(f"Stderr:\n{e.stderr.strip()}")
    except Exception as e:
        log.info(f"An unexpected error occurred while running after download script for '{final_path}': {e}", exc_info=True)
        log.traceback_(e)
        log.traceback_(traceback.format_exc())