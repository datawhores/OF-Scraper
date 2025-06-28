# ofscraper/utils/args/parse/arguments/program.py
import cloup as click  # Ensure cloup is imported as click
from dotenv import dotenv_values
import os
import json
import yaml


def _load_env_file_callback(ctx, param, values):  # 'value' is now 'values' (a tuple)
    """
    Callback for --env-file option. Loads environment variables from the specified file(s).
    Supports .env, .yaml/.yml, and .json formats.
    Later files in the command line argument list will override earlier ones for conflicting keys.
    """

    if not values:  # If no paths were provided, do nothing
        return

    for value in values:
        if not value:  # Skip empty values if any
            continue

        file_path = os.path.abspath(value)  # Get absolute path
        file_extension = os.path.splitext(file_path)[1].lower()

        try:
            if file_extension == ".env":
                data = dotenv_values(dotenv_path=file_path)
                os.environ.update({str(k): str(v) for k, v in data.items()})  #

            elif file_extension in (".yaml", ".yml"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if not isinstance(data, dict):
                        raise ValueError(
                            "YAML file must contain a dictionary/map at the top level."
                        )
                os.environ.update(
                    {str(k): str(v) for k, v in data.items()}
                )  # Ensure keys/values are strings
            elif file_extension == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError(
                            "JSON file must contain a dictionary/object at the top level."
                        )
                os.environ.update(
                    {str(k): str(v) for k, v in data.items()}
                )  # Ensure keys/values are strings
            else:
                data = dotenv_values(dotenv_path=file_path)
                os.environ.update({str(k): str(v) for k, v in data.items()})  #

        except FileNotFoundError:
            print(
                f"Error: Environment file not found: {click.format_filename(file_path)}",
                err=True,
            )
            ctx.exit(1)  # Exit if file not found
        except (json.JSONDecodeError, yaml.YAMLError, ValueError) as e:
            print(
                f"Error parsing environment file {click.format_filename(file_path)}: {e}",
                err=True,
            )
            ctx.exit(1)
        except Exception as e:
            print(
                f"An unexpected error occurred while loading {click.format_filename(file_path)}: {e}",
                err=True,
            )
            ctx.exit(1)
    print("")
