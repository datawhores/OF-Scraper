import logging
from dotenv import dotenv_values
import os
import json
import yaml
log=logging.getLogger("shared")


def load_env_files(values: list[str] | None):
    """
    Loads environment variables from a list of file paths.
    Supports .env, .yaml/.yml, and .json formats.
    Later files in the list will override earlier ones for conflicting keys.

    Args:
        values (list[str] | None): A list of file paths to load.

    Raises:
        FileNotFoundError: If a specified file path does not exist.
        ValueError: If a YAML or JSON file is malformed or not a dictionary.
        Exception: For other unexpected errors during file processing.
    """
    if not values:  # If no paths were provided, do nothing
        return

    for value in values:
        if not value:
            continue

        file_path = os.path.abspath(value)
        file_extension = os.path.splitext(file_path)[1].lower()

        try:
            data = None
            if file_extension == ".env":
                data = dotenv_values(dotenv_path=file_path)
            elif file_extension in (".yaml", ".yml"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if not isinstance(data, dict):
                        raise ValueError(
                            "YAML file must contain a dictionary/map at the top level."
                        )
            elif file_extension == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError(
                            "JSON file must contain a dictionary/object at the top level."
                        )
            else:
                # Default to .env format if extension is unknown or missing
                data = dotenv_values(dotenv_path=file_path)

            if data:
                # Update os.environ, ensuring all keys and values are strings
                os.environ.update({str(k): str(v) for k, v in data.items()})
                log.info(f"Successfully loaded environment variables from '{file_path}'")

        except FileNotFoundError:
            # Let the caller handle this exception
            log.error(f"Environment file not found: '{file_path}'")
            raise
        except (json.JSONDecodeError, yaml.YAMLError, ValueError) as e:
            # Raise a new, more informative error that includes the file path
            log.error(f"Error parsing environment file '{file_path}': {e}")
            raise ValueError(f"Error parsing environment file '{file_path}': {e}") from e
        except Exception as e:
            # Catch any other unexpected errors and add context before raising
            log.error(f"An unexpected error occurred while loading '{file_path}': {e}")
            raise RuntimeError(f"An unexpected error occurred while loading '{file_path}': {e}") from e

