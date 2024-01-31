import json
from contextlib import contextmanager

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.config.file as config_file


@contextmanager
def config_context():
    try:
        yield
    except FileNotFoundError:
        config_file.make_config()
    except json.JSONDecodeError as e:
        configStr = None
        while True:
            try:
                print("You config.json has a syntax error")
                print(f"{e}\n\n")
                config_prompt = prompts.reset_config_prompt()
                if config_prompt == "manual":
                    configStr = prompts.manual_config_prompt(
                        configStr or config_file.config_string()
                    )
                    config_file.write_config(configStr)
                    config = config_file.open_config()
                elif config_prompt == "reset":
                    config_file.make_config_original()
                break
            except Exception as E:
                continue
