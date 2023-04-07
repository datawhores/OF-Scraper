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
from ..utils.prompts import reset_config_prompt,manual_config_prompt


def read_config():
    p = pathlib.Path.home() / configPath
    if not p.is_dir():
        p.mkdir(parents=True, exist_ok=True)

    config = {}
    while True:
        try:
            with open(p / configFile, 'r') as f:
                configText=f.read()
                config = json.loads(configText)

            try:
                if [*config['config']] != [*get_current_config_schema(config)['config']]:
                    config = auto_update_config(p, config)
            except KeyError:
                raise FileNotFoundError

            break
        except FileNotFoundError:
            file_not_found_message = f"You don't seem to have a `config.json` file. One has been automatically created for you at: '{p / configFile}'"
            make_config(p)
            console.print(file_not_found_message)
        except json.JSONDecodeError as e:
            print("You config.json has a syntax error")
            if reset_config_prompt()=="Reset Default":
                make_config(p)
            else:
                print(f"{e}\n\n")
                try:
                    make_config(p, manual_config_prompt(configText))
                except:
                   continue
    return config


def get_current_config_schema(config: dict) -> dict:
    config = config['config']

    new_config = {
        'config': {
            mainProfile: config.get(mainProfile) or mainProfile,
            'save_location': config.get('save_location') or str(pathlib.Path.home() /'Data/ofscraper'),
            'file_size_limit': config.get('file_size_limit') or '',
            'dir_format': config.get("dir_format") or '{model_username}/{responsetype}/{mediatype}/',
            'file_format': config.get('file_format') or '{filename}.{ext}',
            'textlength':config.get('textlength') or 0,
            'date': config.get('date') or  "MM-DD-YYYY",
            "metadata": config.get('metadata') or "{configpath}/{profile}/.data/{username}_{model_id}",
            "filter":config.get('filter') or ""
        }
    }
    return new_config


def make_config(path, config=None):
    config = config or  {
        'config': {
            "mainProfile": mainProfile,
            'save_location': str(pathlib.Path.home() /'Data/ofscraper'),
            'file_size_limit': '',
            'dir_format':'{model_username}/{responsetype}/{mediatype}/',
            'file_format': '{filename}.{ext}',
            'textlength':0,
            'date':"MM-DD-YYYY",
            'metadata':"{configpath}/{profile}/.data/{username}_{model_id}",
            "filter":""
        }
    }
    if isinstance(config,str):
        config=json.loads(config)

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
    try:
        p = pathlib.Path.home() / configPath / configFile

        with open(p, 'r') as f:
            configText=f.read()
            config = json.loads(configText)

        updated_config = {
            'config': config_prompt(config['config'])
        }

        with open(p, 'w') as f:
            f.write(json.dumps(updated_config, indent=4))

        console.print('`config.json` has been successfully edited.')
    except FileNotFoundError:
        make_config(p)
    except json.JSONDecodeError as e:
            while True:
                try:
                    print("You auth.json has a syntax error")
                    print(f"{e}\n\n")
                    with open(p,"w") as f:
                        f.write(manual_config_prompt(configText))
                    with open(p, 'r') as f:
                        configText=f.read()
                        config = json.loads(configText)
                    break
                except:
                    continue
