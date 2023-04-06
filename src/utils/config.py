r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import json
import pathlib
from rich.console import Console
console=Console()
from .prompts import config_prompt
from ..constants import configPath, configFile, mainProfile


def read_config():
    p = pathlib.Path.home() / configPath
    if not p.is_dir():
        p.mkdir(parents=True, exist_ok=True)

    config = {}
    while True:
        try:
            with open(p / configFile, 'r') as f:
                config = json.load(f)

            try:
                if [*config['config']] != [*get_current_config_schema(config)['config']]:
                    config = auto_update_config(p, config)
            except KeyError:
                raise FileNotFoundError

            break
        except FileNotFoundError:
            file_not_found_message = f"You don't seem to have a `config.json` file. One has been automatically created for you at: '{p / configFile}'"

            make_config(p, config)
            console.print(file_not_found_message)
    return config


def get_current_config_schema(config: dict) -> dict:
    config = config['config']

    new_config = {
        'config': {
            mainProfile: config.get(mainProfile) or mainProfile,
            'save_location': config.get('save_location') or '',
            'file_size_limit': config.get('file_size_limit') or '',
            'dir_format': config.get("dir_format") or '{model_username}/{responsetype}/{mediatype}/',
            'file_format': config.get('file_format') or '{filename}.{ext}',
            'textlength':config.get('textlength') or 0,
            'date': config.get('date') or  "MM-DD-YYYY"
        }
    }
    return new_config


def make_config(path, config):
    config = {
        'config': {
            mainProfile: mainProfile,
            'save_location': '',
            'file_size_limit': '',
            'dir_format':'{model_username}/{responsetype}/{mediatype}/',
            'file_format': '{filename}.{ext}',
            'textlength':0,
            'date':"MM-DD-YYYY"
        }
    }

    with open(path / configFile, 'w') as f:
        f.write(json.dumps(config, indent=4))


def update_config(field: str, value):
    p = pathlib.Path.home() / configPath / configFile

    with open(p, 'r') as f:
        config = json.load(f)

    config['config'].update({field: value})

    with open(p, 'w') as f:
        f.write(json.dumps(config, indent=4))


def auto_update_config(path, config: dict) -> dict:
    console.print("Auto updating...")
    new_config = get_current_config_schema(config)

    with open(path / configFile, 'w') as f:
        f.write(json.dumps(new_config, indent=4))

    return new_config


def edit_config():
    p = pathlib.Path.home() / configPath / configFile

    with open(p, 'r') as f:
        config = json.load(f)

    updated_config = {
        'config': config_prompt(config['config'])
    }

    with open(p, 'w') as f:
        f.write(json.dumps(updated_config, indent=4))

    console.print('`config.json` has been successfully edited.')
