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
from ..constants import configPath, configFile, mainProfile,DIR_FORMAT_DEFAULT,METADATA_DEFAULT,FILE_FORMAT_DEFAULT\
,FILE_SIZE_DEFAULT,SAVE_LOCATION_DEFAULT,DATE_DEFAULT,TEXTLENGTH_DEFAULT,FILTER_DEFAULT\
,PROFILE_DEFAULT
import src.prompts.prompts as prompts 


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
            if prompts.reset_config_prompt()=="Reset Default":
                make_config(p)
            else:
                print(f"{e}\n\n")
                try:
                    make_config(p, prompts.manual_config_prompt(configText))
                except:
                   continue
    return config


def get_current_config_schema(config: dict) -> dict:
    config = config['config']

    new_config = {
        'config': {
            mainProfile: config.get(mainProfile) or mainProfile,
            'save_location':get_save_location(config) ,
            'file_size_limit': get_filesize(config),
            'dir_format': get_dirformat(config),
            'file_format':get_fileformat(config),
            'textlength':get_textlength(config),
            'date': get_date(config),
            "metadata": get_metadata(config),
            "filter":get_filter(config)
        }
    }
    return new_config


def make_config(path, config=None):
    config = config or  {
        'config': {
            "mainProfile": mainProfile,
            'save_location': SAVE_LOCATION_DEFAULT,
            'file_size_limit':FILE_SIZE_DEFAULT,
            'dir_format':DIR_FORMAT_DEFAULT,
            'file_format': FILE_FORMAT_DEFAULT,
            'textlength':TEXTLENGTH_DEFAULT,
            'date':DATE_DEFAULT,
            'metadata':METADATA_DEFAULT,
            "filter":FILTER_DEFAULT
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
            'config': prompts.config_prompt(config['config'])
        }

        with open(p, 'w') as f:
            f.write(json.dumps(updated_config, indent=4))

        console.print('`config.json` has been successfully edited.')
    except FileNotFoundError:
        make_config(p)
    except json.JSONDecodeError as e:
            while True:
                try:
                    print("You config.json has a syntax error")
                    print(f"{e}\n\n")
                    with open(p,"w") as f:
                        f.write(prompts.manual_config_prompt(configText))
                    with open(p, 'r') as f:
                        configText=f.read()
                        config = json.loads(configText)
                    break
                except:
                    continue


def get_save_location(config):
    return config.get('save_location') or SAVE_LOCATION_DEFAULT

def get_main_profile(config):
    return config.get('main_profile',PROFILE_DEFAULT)

def get_filesize(config):
    try:
        return int(config.get('file_size_limit', FILE_SIZE_DEFAULT))
    except:
        return 0

def get_dirformat(config):
    return config.get('dir_format', DIR_FORMAT_DEFAULT)

def get_fileformat(config):
    return config.get('file_format', FILE_FORMAT_DEFAULT)

def get_textlength(config):
    try:
        return config.get('textlength', TEXTLENGTH_DEFAULT)
    except:
        return 0

def get_date(config):
    return config.get('date', DATE_DEFAULT)

def get_metadata(config):
    return config.get('metadata', METADATA_DEFAULT)

def get_filter(config):
    filter=config.get('filter', FILTER_DEFAULT)
    if isinstance(filter,str):
        return list(map(lambda x:x.capitalize().strip(),filter.split(",")))
    elif isinstance(filter,list):
        return list(map(lambda x:x.capitalize(),filter))
    else:
        FILTER_DEFAULT