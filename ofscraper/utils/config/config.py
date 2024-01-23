r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import json
import logging

from humanfriendly import parse_size

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.binaries as binaries
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.schema as schema
import ofscraper.utils.console as console_
import ofscraper.utils.paths.common as common_paths

console = console_.get_shared_console()
log = logging.getLogger("shared")


def read_config(update=True):
    config = {}
    while True:
        try:
            config = config_file.open_config()
            try:
                if update and schema.config_diff(config):
                    config = config_file.auto_update_config(config)
            except KeyError:
                raise FileNotFoundError

            break
        except FileNotFoundError:
            file_not_found_message = f"You don't seem to have a `config.json` file. One has been automatically created for you at'"
            config_file.make_config()
            console.print(file_not_found_message)
        except json.JSONDecodeError as e:
            print("You config.json has a syntax error")
            print(f"{e}\n\n")
            if prompts.reset_config_prompt() == "Reset Default":
                config_file.make_config()
            else:
                print(f"{e}\n\n")
                try:
                    config_file.make_config(prompts.manual_config_prompt(config))
                except:
                    continue
    return config


def update_config(field: str, value):
    p = common_paths.get_config_path()
    with open(p, "r") as f:
        config = json.load(f)

    config["config"].update({field: value})

    with open(p, "w") as f:
        f.write(json.dumps(config, indent=4))


def edit_config():
    try:
        config = config_file.open_config()
        updated_config = prompts.config_prompt()
        config.update(updated_config)
        p = common_paths.get_config_path()
        with open(p, "w") as f:
            f.write(json.dumps(updated_config, indent=4))

        console.print("`config.json` has been successfully edited.")
    except FileNotFoundError:
        config_file.make_config()
    except json.JSONDecodeError as e:
        while True:
            try:
                print("You config.json has a syntax error")
                print(f"{e}\n\n")
                with open(p, "w") as f:
                    f.write(prompts.manual_config_prompt(configText))
                with open(p, "r") as f:
                    configText = f.read()
                    config = json.loads(configText)
                break
            except:
                continue


def edit_config_advanced():
    try:
        config = config_file.open_config()

        updated_config = prompts.config_prompt_advanced()
        config.update(updated_config)
        with open(p, "w") as f:
            f.write(json.dumps(updated_config, indent=4))

        console.print("`config.json` has been successfully edited.")
    except FileNotFoundError:
        config_file.make_config()
    except json.JSONDecodeError as e:
        while True:
            try:
                print("You config.json has a syntax error")
                print(f"{e}\n\n")
                with open(p, "w") as f:
                    f.write(prompts.manual_config_prompt(configText))
                with open(p, "r") as f:
                    configText = f.read()
                    config = json.loads(configText)
                break
            except:
                continue


def update_mp4decrypt():
    config = {"config": read_config()}
    if prompts.auto_download_mp4_decrypt() == "Yes":
        config["config"]["mp4decrypt"] = binaries.mp4decrypt_download()
    else:
        config["config"]["mp4decrypt"] = prompts.mp4_prompt(config["config"])
    p = common_paths.get_config_path()
    with open(p, "w") as f:
        f.write(json.dumps(config, indent=4))


def update_ffmpeg():
    config = {"config": read_config()}
    if prompts.auto_download_ffmpeg() == "Yes":
        config["config"]["ffmpeg"] = binaries.ffmpeg_download()
    else:
        config["config"]["ffmpeg"] = prompts.ffmpeg_prompt((config["config"]))
    p = common_paths.get_config_path()
    with open(p, "w") as f:
        f.write(json.dumps(config, indent=4))
