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
import logging
from rich.console import Console
import ofscraper.constants as constants
import ofscraper.prompts.prompts as prompts 

console=Console()
log=logging.getLogger(__package__)

def read_config():
    p = pathlib.Path.home() / constants.configPath
    if not p.is_dir():
        p.mkdir(parents=True, exist_ok=True)

    config = {}
    while True:
        try:
            with open(p / constants.configFile, 'r') as f:
                configText=f.read()
                config = json.loads(configText)

            try:
                if [*config['config']] != [*get_current_config_schema(config)['config']]:
                    config = auto_update_config(p, config)
            except KeyError:
                raise FileNotFoundError

            break
        except FileNotFoundError:
            file_not_found_message = f"You don't seem to have a `config.json` file. One has been automatically created for you at: '{p / constants.configFile}'"
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
    return config["config"]


def get_current_config_schema(config: dict) -> dict:
    config = config['config']

    new_config = {
        'config': {
            constants.mainProfile: get_main_profile(config),
            'save_location':get_save_location(config) ,
            'file_size_limit': get_filesize(config),
            'dir_format': get_dirformat(config),
            'file_format':get_fileformat(config),
            'textlength':get_textlength(config),
            'date': get_date(config),
            "metadata": get_metadata(config),
            "filter":get_filter(config),
            "mp4decrypt":get_mp4decrypt(config),
            "ffmpeg":get_ffmpeg(config),
             "discord":get_discord(config),
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
            constants.mainProfile: constants.mainProfile,
            'save_location': get_save_location(config),
            'file_size_limit':get_filesize(config),
            'dir_format':get_dirformat(config),
            'file_format': get_fileformat(config),
            'textlength':get_textlength(config),
            'date':get_date(config),
            'metadata':get_metadata(config),
            "filter":get_filter(config),
            "mp4decrypt":get_mp4decrypt(config=None),
            "ffmpeg":get_ffmpeg(config),
            "discord":get_discord(config=None),
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

    with open(path / constants.configFile, 'w') as f:
        f.write(json.dumps(config, indent=4))


def update_config(field: str, value):
    p = pathlib.Path.home() / constants.configPath / constants.configFile

    with open(p, 'r') as f:
        config = json.load(f)

    config['config'].update({field: value})

    with open(p, 'w') as f:
        f.write(json.dumps(config, indent=4))


def auto_update_config(path, config: dict) -> dict:
    log.warning("Auto updating config...")
    new_config = get_current_config_schema(config)

    with open(path / constants.configFile, 'w') as f:
        f.write(json.dumps(new_config, indent=4))

    return new_config


def edit_config():
    try:
        p = pathlib.Path.home() / constants.configPath / constants.configFile
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

def update_mp4decrypt():
    config={"config":read_config()}
    config["config"]["mp4decrypt"]=prompts.mp4_prompt(config)
    p = pathlib.Path.home() / constants.configPath / constants.configFile
    with open(p, 'w') as f:
        f.write(json.dumps(config, indent=4))

def update_ffmpeg():
    config={"config":read_config()}
    config["config"]["ffmpeg"]=prompts.ffmpeg_prompt(config)
    p = pathlib.Path.home() / constants.configPath / constants.configFile
    with open(p, 'w') as f:
        f.write(json.dumps(config, indent=4))

    
def get_save_location(config=None):
    if config==None:
        return constants.SAVE_PATH_DEFAULT   
    return config.get('save_location') or constants.SAVE_PATH_DEFAULT

def get_main_profile(config=None):
    if config==None:
        return constants.PROFILE_DEFAULT   
    return config.get('main_profile',constants.PROFILE_DEFAULT)

def get_filesize(config=None):
    if config==None:
        return constants.FILE_SIZE_DEFAULT      
    try:
        return int(config.get('file_size_limit', constants.FILE_SIZE_DEFAULT))
    except:
        return 0

def get_dirformat(config=None):
    if config==None:
        return constants.DIR_FORMAT_DEFAULT     
    return config.get('dir_format', constants.DIR_FORMAT_DEFAULT)

def get_fileformat(config=None):
    if config==None:
        return constants.FILE_FORMAT_DEFAULT     
    return config.get('file_format', constants.FILE_FORMAT_DEFAULT)

def get_textlength(config=None):
    if config==None:
        return constants.TEXTLENGTH_DEFAULT    
    try:
        return int(config.get('textlength', constants.TEXTLENGTH_DEFAULT))
    except:
        return 0

def get_date(config=None):
    if config==None:
        return constants.DATE_DEFAULT     
    return config.get('date', constants.DATE_DEFAULT)

def get_metadata(config=None):
    if config==None:
        return constants.METADATA_DEFAULT      
    return config.get('metadata', constants.METADATA_DEFAULT)

def get_mp4decrypt(config=None):
    if config==None:
        return constants.MP4DECRYPT_DEFAULT    
    return config.get('mp4decrypt', constants.MP4DECRYPT_DEFAULT) or ""

def get_ffmpeg(config=None):
    if config==None:
        return constants.FFMPEG_DEFAULT  
    return config.get('ffmpeg', constants.FFMPEG_DEFAULT) or ""

def get_discord(config=None):
    if config==None:
        return constants.DISCORD_DEFAULT   
    return config.get('discord', constants.DISCORD_DEFAULT ) or ""
def get_filter(config=None):
    if config==None:
        return constants.FILTER_DEFAULT
    filter=config.get('filter', constants.FILTER_DEFAULT)
    if isinstance(filter,str):
        return list(map(lambda x:x.capitalize().strip(),filter.split(",")))
    elif isinstance(filter,list):
        return list(map(lambda x:x.capitalize(),filter))
    else:
        constants.FILTER_DEFAULT
def get_timeline_responsetype(config=None):
    if config==None:
        return constants.RESPONSE_TYPE_DEFAULT["timeline"]
    return config.get('responsetype',{}).get("timeline") or config.get('responsetype',{}).get("post") or constants.RESPONSE_TYPE_DEFAULT["timeline"]

def get_archived_responsetype(config=None):
    if config==None:
        return constants.RESPONSE_TYPE_DEFAULT["archived"]
    return config.get('responsetype',{}).get("archived") or constants.RESPONSE_TYPE_DEFAULT["archived"]

def get_stories_responsetype(config=None):
    if config==None:
        return constants.RESPONSE_TYPE_DEFAULT["stories"]    
    return config.get('responsetype',{}).get("stories") or constants.RESPONSE_TYPE_DEFAULT["stories"]

def get_highlights_responsetype(config=None):
    if config==None:
        return constants.RESPONSE_TYPE_DEFAULT["highlights"]       
    return config.get('responsetype',{}).get("highlights") or constants.RESPONSE_TYPE_DEFAULT["highlights"]

def get_paid_responsetype(config=None):
    if config==None:
        return constants.RESPONSE_TYPE_DEFAULT["paid"]       
    return config.get('responsetype',{}).get("paid") or constants.RESPONSE_TYPE_DEFAULT["paid"]

def get_messages_responsetype(config=None):
    if config==None:
        return constants.RESPONSE_TYPE_DEFAULT["message"]      
    return config.get('responsetype',{}).get("message") or constants.RESPONSE_TYPE_DEFAULT["message"]


def get_profile_responsetype(config=None):
    if config==None:
        return constants.RESPONSE_TYPE_DEFAULT["profile"]       
    return config.get('responsetype',{}).get("profile") or constants.RESPONSE_TYPE_DEFAULT["profile"]


def get_pinned_responsetype(config=None):
    if config==None:
        return constants.RESPONSE_TYPE_DEFAULT["pinned"]       
    return config.get('responsetype',{}).get("pinned") or constants.RESPONSE_TYPE_DEFAULT["pinned"]