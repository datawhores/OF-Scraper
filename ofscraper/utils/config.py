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
from diskcache import JSONDisk,Disk
import ofscraper.constants as constants
import ofscraper.prompts.prompts as prompts 
import ofscraper.utils.binaries as binaries
import ofscraper.utils.paths as paths_
import ofscraper.utils.console as console_
from humanfriendly import parse_size

console=console_.get_shared_console()
log=logging.getLogger("shared")

def get_config_folder():
    out=paths_.get_config_path().parent
    out.mkdir(exist_ok=True,parents=True)
    return out

def read_config():
    p = pathlib.Path(paths_.get_config_path())
    if not p.parent.is_dir():
        p.parent.mkdir(parents=True, exist_ok=True)

    config = {}
    while True:
        try:
            with open(p , 'r') as f:
                configText=f.read()
                config = json.loads(configText)

            try:
                if [*config['config']] != [*get_current_config_schema(config)['config']]:
                    config = auto_update_config(p, config)
            except KeyError:
                raise FileNotFoundError

            break
        except FileNotFoundError:
            file_not_found_message = f"You don't seem to have a `config.json` file. One has been automatically created for you at: '{p}'"
            make_config(p)
            console.print(file_not_found_message)
        except json.JSONDecodeError as e:
            print("You config.json has a syntax error")
            print(f"{e}\n\n")
            if prompts.reset_config_prompt()=="Reset Default":
                make_config(p)
            else:
                print(f"{e}\n\n")
                try:
                    make_config(p, prompts.manual_config_prompt(configText))
                except:
                   continue
    return config["config"]


def get_current_config_schema(config:dict=None) -> dict:
    
    if config:
        config = config['config']

    new_config = {
        'config': {
            constants.mainProfile: get_main_profile(config),
            'save_location':get_save_location(config) ,
            'file_size_limit': get_filesize_limit(config),
            'file_size_min': get_filesize_min(config),
            'dir_format': get_dirformat(config),
            'file_format':get_fileformat(config),
            'textlength':get_textlength(config),
            'space-replacer':get_spacereplacer(config),
            'date': get_date(config),
            "metadata": get_metadata(config),
            "filter":get_filter(config),
            "threads":get_threads(config),
            "code-execution":get_allow_code_execution(config),
            "custom":get_custom(config),
            "mp4decrypt":get_mp4decrypt(config),
            "ffmpeg":get_ffmpeg(config),
             "discord":get_discord(config),
             "private-key":get_private_key(config),
             "client-id":get_client_id(config),
            "key-mode-default":get_key_mode(config),
            "keydb_api":get_keydb_api(config),
            "dynamic-mode-default":get_dynamic(config),
            "partfileclean":get_part_file_clean(config),
            "backend":get_backend(config),
            "download-sems":get_download_semaphores(config),
            "maxfile-sem":get_maxfile_semaphores(config),
            "downloadbars":get_show_downloadprogress(config),
            "cache-mode":cache_mode_helper(config),


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
    config = get_current_config_schema(config) 
    
    if isinstance(config,str):
        config=json.loads(config)
        

    with open(path, 'w') as f:
        f.write(json.dumps(config, indent=4))


def update_config(field: str, value):
    p = paths_.get_config_path() 
    with open(p, 'r') as f:
        config = json.load(f)

    config['config'].update({field: value})

    with open(p, 'w') as f:
        f.write(json.dumps(config, indent=4))


def auto_update_config(path, config: dict) -> dict:
    log.error("Auto updating config...")
    new_config = get_current_config_schema(config)

    with open(path , 'w') as f:
        f.write(json.dumps(new_config, indent=4))

    return new_config


def edit_config():
    try:
        p = paths_.get_config_path()
        log.info(f"config path: {p}")
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

def edit_config_advanced():
    try:
        p = paths_.get_config_path()
        log.info(f"config path: {p}")
        with open(p, 'r') as f:
            configText=f.read()
            config = json.loads(configText)

        updated_config = {
            'config': prompts.config_prompt_advanced(config['config'])
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
    if prompts.auto_download_mp4_decrypt()=="Yes":
        config["config"]["mp4decrypt"]=binaries.mp4decrypt_download()
    else:
        config["config"]["mp4decrypt"]=prompts.mp4_prompt(config["config"])
    p = paths_.get_config_path() 
    with open(p, 'w') as f:
        f.write(json.dumps(config, indent=4))

def update_ffmpeg():
    config={"config":read_config()}
    if prompts.auto_download_ffmpeg()=="Yes":
        config["config"]["ffmpeg"]=binaries.ffmpeg_download()
    else:
        config["config"]["ffmpeg"]=prompts.ffmpeg_prompt((config["config"]))
    p = paths_.get_config_path() 
    with open(p, 'w') as f:
        f.write(json.dumps(config, indent=4))

    
def get_save_location(config=None):
    if config==None:
        return constants.SAVE_PATH_DEFAULT   
    return config.get('save_location') or constants.SAVE_PATH_DEFAULT

def get_main_profile(config=None):
    if config==None:
        return constants.PROFILE_DEFAULT   
    return config.get(constants.mainProfile,constants.PROFILE_DEFAULT) or constants.PROFILE_DEFAULT  

def get_filesize_limit(config=None):
    if config==None:
        return constants.FILE_SIZE_LIMIT_DEFAULT      
    try:
        return parse_size(str(config.get('file_size_limit', constants.FILE_SIZE_LIMIT_DEFAULT  )))
    except:
        return 0


def get_filesize_min(config=None):
    if config==None:
        return constants.FILE_SIZE_MIN_DEFAULT       
    try:
        return parse_size(str(config.get('file_size_min', constants.FILE_SIZE_MIN_DEFAULT  )))
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
def get_allow_code_execution(config=None):
    if config==None:
        return constants.CODE_EXECUTION_DEFAULT  
    return config.get('code-execution', constants.CODE_EXECUTION_DEFAULT)
def get_metadata(config=None):
    if config==None:
        return constants.METADATA_DEFAULT      
    return config.get('metadata', constants.METADATA_DEFAULT)
def get_threads(config=None):
    if config==None:
        return constants.THREADS_DEFAULT  
    threads=config.get('threads', None)
    if threads==None or threads=="":threads=int(constants.THREADS_DEFAULT)
    else:
        try:
            threads=int(threads)
        except:
            threads=int(constants.THREADS_DEFAULT)
    return threads

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

def get_post_responsetype(config=None):
    if config==None:
        return constants.RESPONSE_TYPE_DEFAULT["timeline"]
    return  config.get('responsetype',{}).get("post") or config.get('responsetype',{}).get("timeline") or constants.RESPONSE_TYPE_DEFAULT["timeline"]



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
def get_spacereplacer(config=None):
    if config==None:
        return " "      
    return config.get('space-replacer'," ") or " "

def get_custom(config=None):
    if config==None:
        return None 
    return config.get('custom')
def get_private_key(config=None):
    if config==None:
        return None 
    return config.get('private-key')

def get_client_id(config=None):
    if config==None:
        return None 
    return config.get('client-id')

def get_key_mode(config=None):
    if config==None:
        return constants.KEY_DEFAULT
    value=config.get("key-mode-default")
    return value.lower() if value and value.lower() in set(constants.KEY_OPTIONS) else constants.KEY_DEFAULT
def get_keydb_api(config=None):
    if config==None:
        return ""
    return config.get("keydb_api","") or ""
def get_dynamic(config=None):
    if config==None:
        return constants.DYNAMIC_DEFAULT
    value=config.get("dynamic-mode-default")
    return value.lower() if value and value.lower() in set(["deviint","digitalcriminals"]) else "deviint"
def get_part_file_clean(config=None):
    if config==None:
        return False
    return config.get("partfileclean",False) or False


def get_backend(config=None):
    if config==None:
        return "aio"
    return config.get("backend",constants.BACKEND_DEFAULT) or constants.BACKEND_DEFAULT

def get_download_semaphores(config=None):
    if config==None:
        return constants.DOWNLOAD_SEM_DEFAULT
    sems=config.get('download-sems', None)
    if sems==None or sems=="":sems=int(constants.DOWNLOAD_SEM_DEFAULT)
    else:
        try:
            sems=int(sems)
        except:
            sems=int(constants.DOWNLOAD_SEM_DEFAULT)
    return sems
    
    
    

def get_maxfile_semaphores(config=None):
    if config==None:
        return constants.MAXFILE_SEMAPHORE
    try:
        return int(config.get('maxfile-sem', constants.MAXFILE_SEMAPHORE))
    except:
        return constants.MAXFILE_SEMAPHORE

def get_show_downloadprogress(config):
    if config==None:
        return constants.PROGRESS_DEFAULT
    return config.get("downloadbars",constants.PROGRESS_DEFAULT) or constants.PROGRESS_DEFAULT

def get_cache_mode(config):
    if cache_mode_helper(config)=="sqlite":
        return Disk
    else:
        return JSONDisk


def cache_mode_helper(config):
    if config==None:
        return constants.CACHEDEFAULT
    data= config.get("cache-mode",constants.CACHEDEFAULT)
    if data in [constants.CACHEDEFAULT,"json"]:return data
    else:return constants.CACHEDEFAULT
   

    
