# # hatch_hooks.py
# #!/usr/bin/python3
# import subprocess
# import os
# from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# class CustomHook(BuildHookInterface):
#     def initialize(self, version, build_data):
#         # This method runs at the start of the build process.
#         print("--- Custom Build Hook is Running! ---")

#         # Check if the version is already set by an environment variable
#         if "HATCH_VCS_PRETEND_VERSION" in os.environ:
#             print("--> Version already set by environment. Skipping hook.")
#             return

#         print("--> Running custom versioning hook...")

#         # Run your shell script to get the version
#         # The script will export the variable, but that won't affect this Python process.
#         # So instead, we capture the script's final output.
#         command = "source ./release_version.sh && echo $HATCH_VCS_PRETEND_VERSION"
#         result = subprocess.run(
#             command,
#             shell=True,
#             capture_output=True,
#             text=True,
#             executable="/bin/bash" # Explicitly use bash
#         )

#         if result.returncode != 0:
#             raise Exception(f"release_version.sh failed: {result.stderr}")

#         # Get the version from the last line of the script's output
#         final_version = result.stdout.strip().split('\n')[-1]
#         print(f"--> Version determined by script: {final_version}")

#         # THIS IS THE KEY PART:
#         # We tell hatchling what the final version should be.
#         self.config['version'] = final_version
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from pathlib import Path
from typing import Any, override
class CustomBuildHook(BuildHookInterface):
    @override
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        print(f"Executing from {Path.cwd()}")