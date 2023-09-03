r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import sys
import re
import os
import json
import logging
from rich.console import Console
import arrow
from diskcache import Cache
from InquirerPy.resolver import prompt
from InquirerPy.separator import Separator
from InquirerPy.base import Choice
from InquirerPy.validator import EmptyInputValidator,PathValidator
import ofscraper.constants as constants
import ofscraper.prompts.prompt_strings as prompt_strings
import ofscraper.prompts.prompt_validators as prompt_validators
import ofscraper.utils.config as config
import ofscraper.utils.args as args_
import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.system as system
import ofscraper.utils.paths as paths


console=Console()
def main_prompt() -> int:
    main_prompt_choices = [*constants.mainPromptChoices]
    main_prompt_choices.insert(3, Separator())
    answer=promptClasses.getChecklistSelection(           
            message= 'What would you like to do?',
            choices = [*main_prompt_choices]
    )
    return constants.mainPromptChoices[answer]

def areas_prompt() -> list:
    name="value"
    answers=promptClasses.batchConverter(* [
        {
            'type': 'checkbox',
            'qmark': '[?]',
            'name': name,
            'message': 'Which area(s) would you like to scrape?',
             "validate":prompt_validators.emptyListValidator(),
            'choices': [
                Choice("Profile"),
                Choice('Timeline'),
                Choice('Pinned'),
                Choice('Archived'),
                Choice('Highlights'),
                Choice('Stories'),
                Choice('Messages'),
                Choice("Purchased"),
                Choice("Labels")
            ]

        }
    ])
    return answers[name]


def like_areas_prompt() -> list:
    name = 'areas'

    answers=promptClasses.batchConverter(*[
        {
            'type': 'checkbox',
            'qmark': '[?]',
            'name': name,
            'message': 'Which area(s) would you to perform like/unlike actions on',
             "validate":prompt_validators.emptyListValidator(),
            'choices': [
                Choice('Timeline'),
                Choice('Pinned'),
                Choice('Archived'),
            ]

        }
    ])
    return answers[name]

def scrape_paid_prompt():
    name="value"
    answer=promptClasses.batchConverter(*[
      
        {
            'type': 'list',
            "name":name,
            'message': "Scrape entire paid page\n\n[Warning: initial Scan can be slow]\n[Caution: You should not need this unless your looking to scrape paid content from a deleted/banned model]",
            'choices':[Choice(True,"True"),Choice(False,"False",enabled=True)],
            'long_instruction': prompt_strings.SCRAPE_PAID,
            "default":False

        },

    ])

    return answer[name]

def auth_prompt(auth) -> dict:
    answers = promptClasses.batchConverter(*[
        {
            'type': 'input',
            'name': 'sess',
            'message': 'Enter your sess cookie:',
            'default': auth['sess']
            ,'validate':EmptyInputValidator()
              ,'multiline':True
              

        },
        {
            'type': 'input',
            'name': 'auth_id',
            'message': 'Enter your auth_id cookie:',
            'default': auth['auth_id']
            ,'validate':EmptyInputValidator()
              ,'multiline':True
        },
        {
            'type': 'input',
            'name': 'auth_uid_',
            'message': 'Enter your auth_uid cookie (leave blank if you don\'t use 2FA):',
            'default': auth['auth_uid_']
              ,'multiline':True
        },
        {
            'type': 'input',
            'name': 'user_agent',
            'message': 'Enter your `user agent`:',
            'default': auth['user_agent']
            ,'validate':EmptyInputValidator()
              ,'multiline':True
        },
        {
            'type': 'input',
            'name': 'x-bc',
            'message': 'Enter your `x-bc` token:',
            'default': auth['x-bc']
            ,'validate':EmptyInputValidator()
            ,'multiline':True
        }
    ])

    return answers


def ask_make_auth_prompt() -> bool:
    name = 'make_auth'

    questions = promptClasses.batchConverter(*[
        {
            'type': 'confirm',
            'name': name,
            'message': "You don't seem to have an `auth.json` file. Would you like to make one?",
        }
    ])

    return questions[name]

def browser_prompt()->str:
    pythonver=float(f"{sys.version_info[0]}.{sys.version_info[1]}")
    name="browser"
    answer=None

    if pythonver<3.9 or pythonver>=3.11:
        msg="Select how to retrive auth information"
        console.print("\nNote: Browser Extractions only works with default browser profile\n\n")
        answer=promptClasses.batchConverter(*[
            {
                'type': 'list',
                'message':msg ,
                "name":name,
                'choices':["Enter Each Field Manually","Paste From M-rcus\' OnlyFans-Cookie-Helper", Separator(line="-----------\nBrowser Extractions"),"Chrome","Chromium","Firefox","Opera","Opera GX","Edge","Chromium","Brave","Vivaldi","Safari"],
                "default":"Enter Each Field Manually",

            }
        ])
        

    else:
        console.print("\nNote:To enable automatic extraction install ofscraper with python 3.9 or 3.10\n\n")
        msg="Select how to retrive auth information"
        answer= promptClasses.batchConverter(*[
        {
            'type': 'list',
            'message': msg,
            'choices':["Enter Each Field Manually","Paste From Cookie Helper"],
            "default":"Enter Each Field Manually"

        }
    ]  )
      
    return answer[name]
def user_agent_prompt(current):
    name="input"
    questions = promptClasses.batchConverter(*[
        {
            'type': 'input',
            "name":name,
            'message':'Enter User_Agent from browser',
            'default':current,
            'validate':EmptyInputValidator(),
            'filter':lambda x:prompt_validators.cleanTextInput(x)
        }
    ])
    return  questions[name]

def xbc_prompt():
    name="input"
    questions = promptClasses.batchConverter(*[
        {
            'type': 'input',
            "name":name,
            'message':'Enter x-bc request header',
            'instruction':f"\nGo to browser network tools to view\nFor more instructions visit https://github.com/datawhores/ofscraper\n\n"
            ,'validate':EmptyInputValidator(),
            'filter':lambda x:prompt_validators.cleanTextInput(x)
        }
    ])
    return questions[name]




def auth_full_paste():
    name="input"
    questions = promptClasses.batchConverter(*[
        {
            'type': 'input',
            "name":name,
            'message':'Paste Text from Extension',
            "validate": prompt_validators.jsonValidator(),
            "filter":prompt_validators.jsonloader,
            "multiline":True,
             "instruction":\
"""
Cookie Helper Repo:https://github.com/M-rcus/OnlyFans-Cookie-Helper
"""
             

        }
    ])
    return questions[name]
    
def profiles_prompt() -> int:
    name = 'profile'

    questions = promptClasses.batchConverter(*[
        {
            'type': 'list',
            'name': name,
            'message': 'Select one of the following:',
            'choices': [*constants.profilesPromptChoices]
        }
    ])

    return constants.profilesPromptChoices.get(questions[name])


def edit_profiles_prompt(profiles) -> str:
    name = 'edit'

    profile_names = [profile.stem for profile in profiles]

    questions =promptClasses.batchConverter(* [
        {
            'type': 'list',
            'name': name,
            'message': 'Which profile would you like to edit?',
            'choices': [*profile_names]
        }
    ])

    return questions[name]


def new_name_edit_profiles_prompt(old_profile_name) -> str:
    name = 'new_name'

    answer = promptClasses.batchConverter(* [
        {
            'type': 'input',
            'name': name,
            'message': f'What would you like to rename {old_profile_name} to?',
            'validate':prompt_validators.MultiValidator(EmptyInputValidator(),prompt_validators.currentProfilesValidator())
        }
    ])

    return answer[name]

def create_profiles_prompt() -> str:
    name = 'create'

    answer =promptClasses.batchConverter(*  [
        {
            'type': 'input',
            'name': name,
            'message': 
"""
What would you like to name your new profile?
only letters, numbers, and underscores are allowed
""",
            'validate':prompt_validators.MultiValidator(prompt_validators.namevalitator(),prompt_validators.currentProfilesCreationValidator()
)

        }
    ])

    return answer[name]


def get_profile_prompt(profiles: list) -> str:
    name = 'get_profile'

    answer =promptClasses.batchConverter(*  [
        {
            'type': 'list',
            'name': name,
            'message': 'Select Profile',
            'choices':profiles
            ,"validate":prompt_validators.MultiValidator(  prompt_validators.emptyListValidator())
            
          
        }
    ])
    profile = answer[name]
    return profile


def config_prompt_advanced(config_) -> dict:
    threads =promptClasses.batchConverter(* [
        {
            'type': 'number',
            'name': 'threads',
            "message":"Number of Download processes/threads: ",
            'min_allowed':0,
            'max_allowed':os.cpu_count()-1,
             "validate":EmptyInputValidator(),
            'long_instruction':f"Value can be 1-{os.cpu_count()-1}",
             'default':config.get_threads(config_),
        },
        
    ])

    config_.update(threads)

   
    cache = Cache(paths.getcachepath(),disk=config.get_cache_mode(config.read_config()))
    if not cache.get("speed_download") or  promptClasses.getChecklistSelection(choices=["Yes","No"],message="Re-run speedteset",long_instruction="Download Sems max value is based on calculated speed")=="Yes":
        cache.set("speed_download",get_speed(threads))
    max_allowed=cache.get("speed_download")
    cache.close()
 
    


         
    new_settings =promptClasses.batchConverter(*   [{
            'type': 'number',
            'name': 'download-sem',
            "message":"Number of semaphores per thread: ",
            'min_allowed':1,
            'max_allowed':max_allowed,
             "validate":EmptyInputValidator(),
             'long_instruction':f"Value can be 1-{max_allowed}",
             'default':config.get_download_semaphores(config_),
        },

        {
            'type': 'number',
            'name': 'maxfile-sem',
            "message":"Max Number of open files per thread: ",
            'min_allowed':0,
             "validate":EmptyInputValidator(),
             'long_instruction':
             """
             This should be set to 0 in most cases. 
             This basically limits concurrency, and is only useful in very specific cases
             Set to 0 for no limit
             """,
             'default':config.get_maxfile_semaphores(config_),
        },
        {
            'type': 'list',
            'name': 'dynamic-mode-default',
            'message': 'What would you like to use for dynamic rules\nhttps://grantjenks.com/docs/diskcache/tutorial.html#caveats',
            'default': config.get_dynamic(config_),
            'choices':["deviint","digitalcriminals"],
        },
        
            {
            'type': 'list',
            'name': 'cache-mode',
            'message': 'sqlite should be fine unless your using a network drive\nSee',
            'default': config.cache_mode_helper(config_),
            'choices':["sqlite","json"],
        },
        {
            'type': 'list',
            'name': 'key-mode-default',
            'message': 'Make selection for how to retrive long_message',
            'default': config.get_key_mode(config_),
            'choices':constants.KEY_OPTIONS,

        },

     {
            'type': 'input',
            'name': 'keydb_api',
            'message': 'keydb api key:\n',
            "long_instruction":"Required if your using keydb for key-mode",
            'default': config.get_keydb_api(config_) or "",
        },

        {
            'type': 'filepath',
            'name': 'client-id',
            'message': 'Enter path to client id file',
            'default': config.get_client_id(config_) or "",
        },
         {
            'type': 'filepath'  ,
            'name': 'private-key',
            'message': 'Enter path to private-key',
            'default': config.get_private_key(config_)  or "",
        },
        {
            'type': 'list',
            'name': 'backend',
            'choices':[Choice("aio","aiohttp"),Choice("httpx","httpx")],
            'message': 'Select Which Backend you want:\n',
            'default': config.get_backend(config_) or "",
        },
        {
            'type': 'list',
            'name': 'partfileclean',
            'message': 'Enable auto file resume',
            "long_instruction":"Enable this if you don't want to auto resume files, and want .part files auto cleaned",
            'default': config.get_part_file_clean(config_),
            'choices':[Choice(False,"Yes"),Choice(True,"No")],
        },
            {
            'type': 'input',
            'name': 'custom',
            'message': 'edit custom value:\n',
            "long_instruction":"This is a helper value for remapping placeholder values",
            'default':json.dumps(config.get_custom(config_)) if not isinstance(config.get_custom(config_),str) \
            else config.get_custom(config_) or "" ,
        },
        {
            "type":"list",
            "name":"downloadbars",
            "message":"show download progress bars\nThis can have a negative effect on performance with lower threads",
            "default":config.get_show_downloadprogress(config_) ,
            'choices':[Choice(True,"Yes"),Choice(False,"No")]



        }
    ])
    config_.update(new_settings)
    return config_
    

def config_prompt(config_) -> dict:

    answer = promptClasses.batchConverter(*[
        {
            'type': 'input',
            'name': 'main_profile',
            'message': 'What would you like your main profile to be?',
            'default': config.get_main_profile(config_),
            "validate":EmptyInputValidator()
        },
        {
            'type': 'filepath',
            'name': 'save_location',
            'message':"save_location: ",
            'long_instruction': 'Where would you like to set as the root save downloaded directory?',
            'default':config.get_save_location(config_),
            "filter":lambda x:prompt_validators.cleanTextInput(x),
            "validate": PathValidator(is_dir=True)
        },
        {
            'type': 'input',
            'name': 'file_size_limit',
            'message':"file_size_limit: ",
            'long_instruction':
"""
File size limit
input can be int representing bytes
or human readable such as 10mb
Enter 0 for no limit
""",
            'default': str(config.get_filesize_limit(config_)),
            'filter':int,
      
        },

    {
            'type': 'input',
            'name': 'file_size_min',
            'message':"file_size_min: ",
            'long_instruction':
"""
File size min
input can be int representing bytes
or human readable such as 10mb
Enter 0 for no minimum
""",
            'default': str(config.get_filesize_min(config_)),
            'filter':int,
      
        },
           {
            'type': 'input',
            'name': 'dir_format',
            'message':"dir_format: ",
            'long_instruction': 'What format do you want for download directories',
            'default': config.get_dirformat(config_)
        },
              {
            'type': 'input',
            'name': 'file_format',
            'message': 'What format do you want for downloaded files',
            'default':config.get_fileformat(config_),
        },
                     {
            'type': 'number',
            'name': 'textlength',
            'message':"textlength: ",
            'long_instruction': 'Enter the max length to extract for post text, 0 means unlimited\n',
            'default': config.get_textlength(config_),
            'min_allowed':0,
             "validate":EmptyInputValidator()
        },
                {
        'type': 'input',
            'name': 'space-replacer',
            'message':"space-replacer: ",
            'long_instruction': 'Replace any spaces in text with this character\n',
            'default': config.get_spacereplacer(config_),
             "validate":EmptyInputValidator()
        },
         {
            'type': 'input',
            'name': 'date',
            'message': 'date: ',
            "long_instruction":"Enter Date format",
            'default': config.get_date(config_),
             "validate":prompt_validators.dateplaceholdervalidator()
        },
        {
            'type': 'input',
            'name': 'metadata',
            "message":"metadata: ",
            'long_instruction': 'Where should metadata files be saved',
            'default':config.get_metadata(config_),
        },
        {
            'type': 'checkbox',
            'name': 'filter',
            "message":"filter: ",
            'choices':list(map(lambda x:Choice(name=x,value=x, enabled=x.capitalize() in set(config.get_filter(config_))),constants.FILTER_DEFAULT)),
             "validate":prompt_validators.emptyListValidator()
        },
          {
            'type': 'list',
            'name':"code-execution",
            'message': "Enable Code Execution:",
            'choices':[Choice(True,"Yes"),Choice(False,"No",enabled=True)],
            "default":config.get_allow_code_execution(config_),
            "long_instruction":"Be careful if turning this on this only effects file_format,metadata, and dir_format"


        },



        {
            'type': 'filepath',
            'name': 'mp4decrypt',
            "message":"mp4decrypt path: ",
             "validate":prompt_validators.MultiValidator(EmptyInputValidator(),prompt_validators.mp4decryptpathvalidator(),prompt_validators.mp4decryptexecutevalidator()),
            "default":config.get_mp4decrypt(config_),
            "long_instruction":             """
Certain content requires decryption to process please provide the full path to mp4decrypt
"""
        },
        {
                        'type': 'filepath',
            'name': 'ffmpeg',
            "message":"ffmpeg path: ",
             "validate":prompt_validators.MultiValidator(EmptyInputValidator(),prompt_validators.ffmpegpathvalidator(),prompt_validators.ffmpegexecutevalidator()),
             "long_instruction": 
             """
Certain content requires decryption to process please provide the full path to ffmpeg
""",
"default":config.get_ffmpeg(config_)
        
        },

        {
            'type': 'input',
            'name': 'discord',
            "message":"discord webhook: ",
             "validate":prompt_validators.DiscordValidator(),
             "default":config.get_discord(config_)
        },
  
    ])
    console.print("Set mapping for {responsetype} placeholder\n\n")

    answer2 = promptClasses.batchConverter(*[
        {
            'type': 'input',
            'name': 'timeline',
            'long_instruction': 
            """
set responsetype for timeline posts
Empty string is consider to be 'posts'
            """,
            'default': config.get_timeline_responsetype(config_),
            'message':"timeline responsetype mapping: "
        },
             {
            'type': 'input',
            'name': 'archived',
            'long_instruction': 
            """
set responsetype for archived posts
Empty string is consider to be 'archived'
            """,
            'default': config.get_archived_responsetype(config_),
            'message':"archived responsetype mapping: "
        },

    {
            'type': 'input',
            'name': 'pinned',
            'long_instruction': 
            """
set responsetype for pinned posts
Empty string is consider to be 'pinned'
            """,
            'default': config.get_pinned_responsetype(config_),
            'message':"pinned responsetype mapping: "
        },
                     {
            'type': 'input',
            'name': 'message',
            'long_instruction': 
            """
set responsetype for message posts
Empty string is consider to be 'message'
            """,
            'default': config.get_messages_responsetype(config_),
            'message':"message responstype mapping: "
        },
                        {
            'type': 'input',
            'name': 'paid',
            'long_instruction': 
            """
set responsetype for paid posts
Empty string is consider to be 'paid'
            """,
            'default': config.get_paid_responsetype(config_),
            'message':"paid responsetype mapping: "
        },
                             {
    'type': 'input',
            'name': 'stories',
            'long_instruction': 
            """
set responsetype for stories
Empty string is consider to be 'stories'
            """,
            'default': config.get_stories_responsetype(config_),
            'message':"stories responsetype mapping: "
        },
                                    {
    'type': 'input',
            'name': 'highlights',
            'long_instruction': 
            """
set responsetype for highlights
Empty string is consider to be 'highlights'
            """,
            'default': config.get_highlights_responsetype(config_),
            'message':"highlight responsetype mapping: "
        },
                                          {
    'type': 'input',
            'name': 'profile',
            'long_instruction': 
            """
set responsetype for profile
Empty string is consider to be 'profile'
            """,
            'default': config.get_profile_responsetype(config_),
            'message':"profile responsetype mapping: "
        }
     ])
    answer["responsetype"]=answer2
    config_.update(answer)
    return config_
def reset_username_prompt() -> bool:
    name = 'reset username'
    answer =promptClasses.batchConverter(* [
        {
            'type': 'list',
            'name': name,
            'message': "Do you want to reset username selection",
            'choices':["Yes","No"]
        }
    ])

    return answer[name]
def mp4_prompt(config_):
    answer =promptClasses.batchConverter(* [
         {
            'type': 'filepath',
            'name': 'mp4decrypt',
            "message":"mp4decrypt path: ",
             "validate":prompt_validators.MultiValidator(EmptyInputValidator(),prompt_validators.mp4decryptpathvalidator(),prompt_validators.mp4decryptexecutevalidator()),
             "long_instruction": 
             """
Certain content requires decryption to process please provide the full path to mp4decrypt
Linux version [mp4decrypt] and windows version [mp4decrypt.exe] are provided in the repo

https://www.bento4.com/documentation/mp4decrypt/
""",
"default":config.get_mp4decrypt(config_)
        },
    ])

    return answer["mp4decrypt"]

def ffmpeg_prompt(config_):
    answer = promptClasses.batchConverter(*[
         {
            'type': 'filepath',
            'name': 'ffmpeg',
            "message":"ffmpeg path: ",
             "validate":prompt_validators.MultiValidator(EmptyInputValidator(),prompt_validators.ffmpegpathvalidator(),prompt_validators.ffmpegexecutevalidator()),
             "long_instruction": 
             """
Certain content requires decryption to process please provide the full path to ffmpeg
Linux version [ffmpeg] and windows version [ffmpeg.exe] are provided in the repo 

https://ffmpeg.org/download.html
""",
"default":config.get_ffmpeg(config_)
        },
    ])

    return answer["ffmpeg"] 
def auto_download_mp4_decrypt()-> bool:
    name = 'manual download'
    answer = promptClasses.batchConverter(*[
        {
            'type': 'list',
            'name': name,
            'message': "mp4decrypt not found would you like to auto install?",
            'choices':["Yes","No"]
        }
    ])

    return answer[name]

def auto_download_ffmpeg()-> bool:
    name = 'manual download'
    answer = promptClasses.batchConverter(*[
        {
            'type': 'list',
            'name': name,
            'message': "ffmpeg not found would you like to auto install?",
            'choices':["Yes","No"]
        }
    ])
    return answer[name]

def continue_prompt() -> bool:
    name = 'continue'
    answer =promptClasses.batchConverter(* [
        {
            'type': 'list',
            'name': name,
            'message': "Do you want to continue with script",
            'choices':["Yes","No"]
        }
    ])

    return answer[name]
def model_selector(models) -> bool:
    import ofscraper.utils.userselector as userselector
    choices=list(map(lambda x:model_selectorHelper(x[0],x[1])  ,enumerate(models)))
    def funct(prompt):
        userselector.setfilter()
        userselector.setsort()
        models=userselector.filterNSort(userselector.ALL_SUBS)
        choices=list(map(lambda x:model_selectorHelper(x[0],x[1])  ,enumerate(models)))
        selectedSet=set(map(lambda x:re.search("^[0-9]+: ([^ ]+)",x["name"]).group(1),prompt.selected_choices or []))
        for model in choices:
            name=re.search("^[0-9]+: ([^ ]+)",model.name).group(1)
            if name in selectedSet:
                model.enabled=True
        prompt.content_control._raw_choices=choices
        prompt.content_control.choices=prompt.content_control._get_choices(prompt.content_control._raw_choices, prompt.content_control._default)
        prompt.content_control._format_choices()
        return prompt
       
        

    
        
        


        
        
        

    


    p=promptClasses.getFuzzySelection(
                                                            
        choices=choices,
        transformer=lambda result:",".join(map(lambda x:x.split(" ")[1],result)),
        multiselect=True,
        long_instruction=prompt_strings.MODEL_SELECT,
        long_message=prompt_strings.MODEL_FUZZY,
        altx=funct,
        validate=prompt_validators.emptyListValidator(),
        prompt='Filter: ',
        message= "Which models do you want to scrape\n:",

        )
    
    
    
    
    
    return p

def model_selectorHelper(count,x):
    format='YYYY-MM-DD'
    expired=arrow.get(x['expired']).format(format) if x['expired'] else None
    renewed=arrow.get(x['renewed']).format(format)  if x['renewed'] else None
    subscribed=arrow.get(x['subscribed']).format(format)  if x['subscribed'] else None
    price=x["price"] if x["price"]!=None else "Unknown"
    name=x["name"]
    active=x["active"]

    return Choice(x,name=f"{count+1}: {name}  renewed={renewed}  subdate={subscribed}  exprdate={expired} subprice={price} active={active}")
    

def decide_filters_prompt():
    answer = promptClasses.batchConverter(*[
        {
            'type': 'list',
            "name":"input",
            "default":"No",
            'message': "Modify filters for your accounts list?\nSome usage examples are scraping free accounts only or paid accounts without renewal",
            'choices':["Yes","No"]
        }
    ])

    return answer["input"]
def modify_filters_prompt(args):
    answer = promptClasses.batchConverter(*[
        {
            'type': 'list',
            "name":"renewal",
             "default":False,
            'message': "Filter account by whether it has a renewal date",
            'choices':[Choice("active","Active Only"),Choice("disabled","Disabled Only"),Choice(False,"Both")]
        },
        {
            'type': 'list',
            "name":"expire",
             "default":False,
            'message': "Filter accounts based on access to content via a subscription",
            'choices':[Choice("active","Active Only"),Choice("expired","Expired Only"),Choice(False,"Both")]
        },

     
            {
            'type': 'list',
            "name":"subscription",
            'message': "Filter accounts by the type of subscription",
             "default":False,
            'choices':[Choice("paid","Paid Subscriptions Only"),Choice("free","Free Subscriptions Only"),Choice(False,"Both")]
        }
    ])
    args.renewal=answer["renewal"]
    args.sub_status=answer["expire"]
    args.account_type=answer["subscription"]
    return args


def decide_sort_prompt():
    answer = promptClasses.batchConverter(*[
        {
            'type': 'list',
            "name":"input",
            'message': f"Change the Order or the Criteria for how the model list is sorted\nCurrent setting are {'Ascending' if not args_.getargs().desc else 'Descending'} in {args_.getargs().sort.capitalize()} order",
             "default":"No",
            'choices':["Yes","No"]
        }
    ])

    return answer["input"]
def modify_sort_prompt(args):
    answer =promptClasses.batchConverter(* [
        {
            'type': 'list',
            "name":"type",
            'message': "Sort Accounts by..",
            "default":args.desc==False,
            'choices':[Choice("name","By Name"),Choice("subscribed","Subscribed Date"),Choice("expired","Expiring Date"),Choice("price","Price")],
        },
        {
            'type': 'list',
              "name":"order",
            'message': "Sort Direction",
            'choices':[Choice(True,"Ascending"),Choice(False,"Descending",enabled=True)],
            "default":True

        },

    ])

    args.sort=answer["type"]
    args.desc=answer["order"]==False
    return args

def change_default_profile() -> bool:
    name = 'reset username'
    answer = promptClasses.batchConverter(*[
        {
            'type': 'list',
            'name': name,
            'message': "Set this as the new default profile",
            'choices':["Yes","No"]
        }
    ])

    return answer[name]

def reset_config_prompt() -> bool:
    name="input"
    questions = promptClasses.batchConverter(*[
        {
            'type': 'list',
            "name":name,
            'message': "How do you want to fix this issue",
            'choices':["Reset Default","Manually Edit Config"]
        }
    ])
    return questions[name]


def reset_auth_prompt() -> bool:
    name="input"
    questions = promptClasses.batchConverter(*[
        {
            'type': 'list',
            "name":name,
            'message': "How do you want to fix this issue",
            'choices':[Choice("Reset Default","Reset Default"),Choice("Manually Edit Auth Config","Manually Edit Auth Config")]
        }
    ])
    return questions[name]

def manual_config_prompt(configText) -> str:
    name="input"
    
    questions = promptClasses.batchConverter(*[
        
     
        
        
        {
              
            'type': 'input',
            'multiline':True,
            "name":name,
            'default':configText,
            "long_message":prompt_strings.CONFIG_MULTI,
            'message': "Edit config text\n===========\n",
        }
    ])

    return questions[name]
def manual_auth_prompt(authText) -> str:
    name="input"
        
    
    questions = promptClasses.batchConverter(*[
        
        
    
        {
               
            "name":name,
            'type': 'input',
            'multiline':True,
            'default':authText,
            'message': "Edit auth text\n===========\n",
            "long_message":prompt_strings.AUTH_MULTI,
            "validate":EmptyInputValidator()
        }
    ])


    return questions[name]

def get_speed(threads):
    logging.getLogger("shared").info("running speed test")
    speed=system.speed_test()
    thread_count=int(threads["threads"])
    if int(thread_count)==0:max_allowed=max((speed*.6)//constants.maxChunkSize,3)
    else: max_allowed=min(int(max(((speed*.6)/thread_count)//constants.maxChunkSizeB,3)),25)
    return max_allowed