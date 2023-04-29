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
from ..constants import *
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
            mainProfile: get_main_profile(config),
            'save_location':get_save_location(config) ,
            'file_size_limit': get_filesize(config),
            'dir_format': get_dirformat(config),
            'file_format':get_fileformat(config),
            'textlength':get_textlength(config),
            'date': get_date(config),
            "metadata": get_metadata(config),
            "filter":get_filter(config),
            "responsetype":{
           "timeline":get_timeline_responsetype(config),
         "message":get_messages_responsetype(config),
            "archived":get_archived_responsetype(config),
            "paid":get_paid_responsetype(config),
            "stories":get_stories_responsetype(config),
            "highlights":get_highlights_responsetype(config),
            "profile":get_profile_responsetype(config),
            "pinned":get_pinned_responsetype(config)
            }
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
            "filter":FILTER_DEFAULT,
            "responsetype":{
        "timeline":get_timeline_responsetype(config),
         "message":get_messages_responsetype(config),
            "archived":get_archived_responsetype(config),
            "paid":get_paid_responsetype(config),
            "stories":get_stories_responsetype(config),
            "highlights":get_highlights_responsetype(config),
            "profile":get_profile_responsetype(config),
            "pinned":get_pinned_responsetype(config),

            }
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
    console.print("Auto updating config...")
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


def get_save_location(config=None):
    if not config:
        return SAVE_LOCATION_DEFAULT   
    return config.get('save_location') or SAVE_LOCATION_DEFAULT

def get_main_profile(config=None):
    if not config:
        return PROFILE_DEFAULT   
    return config.get('main_profile',PROFILE_DEFAULT)

def get_filesize(config=None):
    if not config:
        return FILE_SIZE_DEFAULT      
    try:
        return int(config.get('file_size_limit', FILE_SIZE_DEFAULT))
    except:
        return 0

def get_dirformat(config=None):
    if not config:
        return DIR_FORMAT_DEFAULT     
    return config.get('dir_format', DIR_FORMAT_DEFAULT)

def get_fileformat(config=None):
    if not config:
        return FILE_FORMAT_DEFAULT     
    return config.get('file_format', FILE_FORMAT_DEFAULT)

def get_textlength(config=None):
    if not config:
        return TEXTLENGTH_DEFAULT    
    try:
        return int(config.get('textlength', TEXTLENGTH_DEFAULT))
    except:
        return 0

def get_date(config=None):
    if not config:
        return DATE_DEFAULT     
    return config.get('date', DATE_DEFAULT)

def get_metadata(config=None):
    if not config:
        return METADATA_DEFAULT      
    return config.get('metadata', METADATA_DEFAULT)


def get_filter(config=None):
    if not config:
        return FILTER_DEFAULT
    filter=config.get('filter', FILTER_DEFAULT)
    if isinstance(filter,str):
        return list(map(lambda x:x.capitalize().strip(),filter.split(",")))
    elif isinstance(filter,list):
        return list(map(lambda x:x.capitalize(),filter))
    else:
        FILTER_DEFAULT
def get_timeline_responsetype(config=None):
    if not config:
        return RESPONSE_TYPE_DEFAULT["timeline"]
    return config.get('responsetype',{}).get("timeline") or config.get('responsetype',{}).get("post") or RESPONSE_TYPE_DEFAULT["timeline"]

def get_archived_responsetype(config=None):
    if not config:
        return RESPONSE_TYPE_DEFAULT["archived"]
    return config.get('responsetype',{}).get("archived") or RESPONSE_TYPE_DEFAULT["archived"]

def get_stories_responsetype(config=None):
    if not config:
        return RESPONSE_TYPE_DEFAULT["stories"]    
    return config.get('responsetype',{}).get("stories") or RESPONSE_TYPE_DEFAULT["stories"]

def get_highlights_responsetype(config=None):
    if not config:
        return RESPONSE_TYPE_DEFAULT["highlights"]       
    return config.get('responsetype',{}).get("highlights") or RESPONSE_TYPE_DEFAULT["highlights"]

def get_paid_responsetype(config=None):
    if not config:
        return RESPONSE_TYPE_DEFAULT["paid"]       
    return config.get('responsetype',{}).get("paid") or RESPONSE_TYPE_DEFAULT["paid"]

def get_messages_responsetype(config=None):
    if not config:
        return RESPONSE_TYPE_DEFAULT["message"]      
    return config.get('responsetype',{}).get("message") or RESPONSE_TYPE_DEFAULT["message"]


def get_profile_responsetype(config=None):
    if not config:
        return RESPONSE_TYPE_DEFAULT["profile"]       
    return config.get('responsetype',{}).get("profile") or RESPONSE_TYPE_DEFAULT["profile"]


def get_pinned_responsetype(config=None):
    if not config:
        return RESPONSE_TYPE_DEFAULT["pinned"]       
    return config.get('responsetype',{}).get("pinned") or RESPONSE_TYPE_DEFAULT["pinned"]