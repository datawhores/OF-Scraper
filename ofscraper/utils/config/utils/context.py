import json
import pathlib
from contextlib import contextmanager

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.config.file as config_file
import ofscraper.utils.paths.common as common_paths


@contextmanager
def config_context():
    while True:
        try:
            p = pathlib.Path(common_paths.get_config_path())
            with open(p, "r") as f:
                json.load(f)
        except FileNotFoundError:
            config_file.make_config()
            continue
        except json.JSONDecodeError as e:
            configStr = None
            while True:
                try:
                    print("Your config.json has a syntax error")
                    import traceback

                    print(traceback.format_exc())
                    print(f"{e}\n\n")
                    config_prompt = prompts.reset_config_prompt()
                    if config_prompt == "manual":
                        configStr = prompts.manual_config_prompt(
                            configStr or config_file.config_string()
                        )
                        config_file.write_config(configStr)
                        config_file.open_config()
                    elif config_prompt == "reset":
                        config_file.make_config_original()
                    break
                except Exception:
                    continue
            continue
        yield
        break
