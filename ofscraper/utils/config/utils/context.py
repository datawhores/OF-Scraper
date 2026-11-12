import json
from ofscraper.prompts.cancel import back_to_menu
import pathlib
from contextlib import contextmanager

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.config.file as config_file
import ofscraper.utils.interactive as interactive
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
                        configStr = _manual_config(configStr or config_file.config_string())
                        if configStr is None:
                            continue
                        config_file.write_config(configStr)
                        config_file.open_config()
                    elif config_prompt == "reset":
                        config_file.make_config_original()
                    break
                except interactive.NoConsoleError:
                    raise  # asking again can't work either
                except Exception:
                    continue
            continue
        yield
        break


@back_to_menu
def _manual_config(configStr):
    return prompts.manual_config_prompt(configStr)
