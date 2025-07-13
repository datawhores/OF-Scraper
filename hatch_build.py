# hatch_build.py
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from pathlib import Path
from typing import Any, override
import subprocess


class CustomBuildHook(BuildHookInterface):
    @override
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        print(f"Executing from {Path.cwd()}")
        command = "source scripts/release_version.sh && echo $HATCH_VCS_PRETEND_VERSION"
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            executable="/bin/bash" # Explicitly use bash
        )
        if result.returncode != 0:
            raise Exception(f"release_version.sh failed: {result.stderr}")

        # Get the version from the last line of the script's output
        final_version = result.stdout.strip().split('\n')[-1]
        print(f"--> Version determined by script: {final_version}")

        # THIS IS THE KEY PART:
        # We tell hatchling what the final version should be.
        self.config['version'] = final_version
