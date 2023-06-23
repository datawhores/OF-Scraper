r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import sys
from rich.console import Console
import pathlib
import re
import arrow
from InquirerPy.resolver import prompt
from InquirerPy import inquirer
from InquirerPy.separator import Separator
from InquirerPy.base import Choice
from InquirerPy import get_style
from InquirerPy.validator import EmptyInputValidator,PathValidator
import ofscraper.constants as constants
import ofscraper.prompts.prompt_strings as prompt_strings
import ofscraper.prompts.prompt_validators as prompt_validators
import ofscraper.utils.config as config
import ofscraper.utils.args as args_

console=Console()
def main_prompt() -> int:
    main_prompt_choices = [*constants.mainPromptChoices]
    main_prompt_choices.insert(3, Separator())

    name = 'action'

    questions = [
        {
            'type': 'list',
            'name': name,
            'message': 'What would you like to do?',
            'choices': [*main_prompt_choices],
        }
    ]

    answer = prompt(questions)
    return constants.mainPromptChoices[answer[name]]










def areas_prompt() -> list:
    name = 'areas'

    questions = [
        {
            'type': 'checkbox',
            'qmark': '[?]',
            'name': name,
            'message': 'Which area(s) would you like to scrape? (Press ENTER to continue)',
             "validate":prompt_validators.emptyListValidator(),
            'choices': [
                Choice("Profile"),
                Choice('Timeline'),
                Choice('Pinned'),
                Choice('Archived'),
                Choice('Highlights'),
                Choice('Stories'),
                Choice('Messages'),
                Choice("Purchased")
            ]
            ,"instruction":prompt_strings.CHECKLISTINSTRUCTIONS,

        }
    ]
    answers = prompt(questions)
    return answers[name]


def like_areas_prompt() -> list:
    name = 'areas'

    questions = [
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
            ,"instruction":prompt_strings.CHECKLISTINSTRUCTIONS,

        }
    ]
    answers = prompt(questions)
    return answers[name]

def scrape_paid_prompt():
    questions = [
        {
            'type': 'list',
            'message': "Scrape entire paid page [WARNING ONLY USE IF NEEDED i.e for DELETED MODELS]",
            'choices':[Choice(True,"True"),Choice(False,"False",enabled=True)],
            'long_instruction': prompt_strings.SCRAPE_PAID,
            "default":False

        },

    ]

    answer = prompt(questions)
    return answer[0]

def auth_prompt(auth) -> dict:
    questions = [
        {
            'type': 'input',
            'name': 'sess',
            'message': 'Enter your sess cookie:',
            'default': auth['sess']
            ,'validate':EmptyInputValidator()

        },
        {
            'type': 'input',
            'name': 'auth_id',
            'message': 'Enter your auth_id cookie:',
            'default': auth['auth_id']
            ,'validate':EmptyInputValidator()
        },
        {
            'type': 'input',
            'name': 'auth_uid_',
            'message': 'Enter your auth_uid cookie (leave blank if you don\'t use 2FA):',
            'default': auth['auth_uid_']
        },
        {
            'type': 'input',
            'name': 'user_agent',
            'message': 'Enter your `user agent`:',
            'default': auth['user_agent']
            ,'validate':EmptyInputValidator()
        },
        {
            'type': 'input',
            'name': 'x-bc',
            'message': 'Enter your `x-bc` token:',
            'default': auth['x-bc']
            ,'validate':EmptyInputValidator()
        }
    ]

    answers = prompt(questions)
    return answers


def ask_make_auth_prompt() -> bool:
    name = 'make_auth'

    questions = [
        {
            'type': 'confirm',
            'name': name,
            'message': "You don't seem to have an `auth.json` file. Would you like to make one?",
        }
    ]

    answer = prompt(questions)
    return answer[name]

def browser_prompt()->str:
    pythonver=float(f"{sys.version_info[0]}.{sys.version_info[1]}")
    msg="Select how to retrive auth information"

    if pythonver<3.9 or pythonver>=3.11:
        console.print("\nNote: Browser Extractions only works with default browser profile\n\n")
        questions = [
            {
                'type': 'list',
                'message':msg ,
                'choices':["Enter Each Field Manually","Paste From Cookie Helper", Separator(line="-----------\nBrowser Extractions"),"Chrome","Chromium","Firefox","Opera","Opera GX","Edge","Chromium","Brave","Vivaldi","Safari"],
                "default":"Enter Each Field Manually",

            }
        ]

    else:
        console.print("\nNote:To enable automatic extraction install ofscraper with python 3.9 or 3.10\n\n")
        msg="Select how to retrive auth information"
        questions = [
        {
            'type': 'list',
            'message': msg,
            'choices':["Enter Each Field Manually","Paste From Cookie Helper"],
            "default":"Enter Each Field Manually"

        }
    ]  
      
    return prompt(questions)[0]
def user_agent_prompt(current):
    questions = [
        {
            'type': 'input',
            'message':'Enter User_Agent from browser',
            'default':current,
            'validate':EmptyInputValidator(),
            'filter':lambda x:prompt_validators.cleanTextInput(x)
        }
    ]
    return  prompt(questions)[0]

def xbc_prompt():
    questions = [
        {
            'type': 'input',
            'message':'Enter x-bc request header',
            'instruction':f"\nGo to browser network tools to view\nFor more instructions visit https://github.com/datawhores/ofscraper\n\n"
            ,'validate':EmptyInputValidator(),
            'filter':lambda x:prompt_validators.cleanTextInput(x)
        }
    ]
    return  prompt(questions)[0]




def auth_full_paste():
    questions = [
        {
            'type': 'input',
            'message':'Paste Text from Extension',
            "validate": prompt_validators.jsonValidator(),
            "filter":prompt_validators.jsonloader,
             "instruction":\
"""
Cookie Helper Repo:https://github.com/M-rcus/OnlyFans-Cookie-Helper
"""
             

        }
    ]
    return prompt(questions)[0]
    
def profiles_prompt() -> int:
    name = 'profile'

    questions = [
        {
            'type': 'list',
            'name': name,
            'message': 'Select one of the following:',
            'choices': [*constants.profilesPromptChoices]
        }
    ]

    answer = prompt(questions)
    return constants.profilesPromptChoices[answer[name]]


def edit_profiles_prompt(profiles) -> str:
    name = 'edit'

    profile_names = [profile.stem for profile in profiles]

    questions = [
        {
            'type': 'list',
            'name': name,
            'message': 'Which profile would you like to edit?',
            'choices': [*profile_names]
        }
    ]

    answer = prompt(questions)
    return answer[name]


def new_name_edit_profiles_prompt(old_profile_name) -> str:
    name = 'new_name'

    questions = [
        {
            'type': 'input',
            'name': name,
            'message': f'What would you like to rename {old_profile_name} to?',
            'validate':prompt_validators.MultiValidator(EmptyInputValidator(),prompt_validators.currentProfilesValidator())
        }
    ]

    answer = prompt(questions)
    return answer[name]

def create_profiles_prompt() -> str:
    name = 'create'

    questions = [
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
    ]

    answer = prompt(questions)
    return answer[name]


def get_profile_prompt(profiles: list) -> str:
    name = 'get_profile'

    questions = [
        {
            'type': 'list',
            'name': name,
            'message': 'Select Profile',
            'choices':profiles
            ,"validate":prompt_validators.MultiValidator(  prompt_validators.emptyListValidator(),prompt_validators.currentProfileDeleteValidator())
            
          
        }
    ]
    answer = prompt(questions)
    profile = answer[name]
    return profile


def config_prompt(config_) -> dict:

    questions = [
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
            'type': 'number',
            'name': 'file_size_limit',
            'message':"file_size_limit: ",
            'long_instruction':
"""
File size limit (enter a value in bytes)
Enter 0 for no limit
""",
            'default': config.get_filesize(config_),
            'filter':int,
             'min_allowed':0,
      
        },
           {
            'type': 'input',
            'name': 'dir_format',
            'message':"dir_format: ",
            'long_instruction': 'What format do you want for download directories',
            'default': config.get_dirformat(config_),
             "validate":prompt_validators.dirformatvalidator()
        },
              {
            'type': 'input',
            'name': 'file_format',
            'message': 'What format do you want for downloaded files',
            'default':config.get_fileformat(config_),
             "validate":prompt_validators.fileformatvalidator()
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
             "validate":prompt_validators.metadatavalidator()
        },
        {
            'type': 'checkbox',
            'name': 'filter',
            "message":"filter: ",
            'choices':list(map(lambda x:Choice(name=x,value=x, enabled=x.capitalize() in set(config.get_filter(config_))),constants.FILTER_DEFAULT)),
             "validate":prompt_validators.emptyListValidator()
        },
        {
            'type': 'number',
            'name': 'threads',
            "message":"Number of Download Theads: ",
            'min_allowed':1,
            'max_allowed':10,
             "validate":EmptyInputValidator(),
             'long_instruction':"Value can be 1-10",
             'default':config.get_threads(config_),
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
  
    ]

    questions2 = [
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
     ]
    answers = prompt(questions)
    console.print("Set mapping for {responsetype} placeholder\n\n")
    answers["responsetype"]=prompt(questions2)
    return answers
def reset_username_prompt() -> bool:
    name = 'reset username'
    questions = [
        {
            'type': 'list',
            'name': name,
            'message': "Do you want to reset username option",
            'choices':["Yes","No"]
        }
    ]

    answer = prompt(questions)
    return answer[name]
def mp4_prompt(config_):
    questions = [
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
    ]

    answer = prompt(questions)
    return answer["mp4decrypt"]

def ffmpeg_prompt(config_):
    questions = [
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
    ]

    answer = prompt(questions)
    return answer["ffmpeg"] 
def auto_download_mp4_decrypt()-> bool:
    name = 'manual download'
    questions = [
        {
            'type': 'list',
            'name': name,
            'message': "mp4decrypt not found would you like to auto install?",
            'choices':["Yes","No"]
        }
    ]

    answer = prompt(questions)
    return answer[name]

def auto_download_ffmpeg()-> bool:
    name = 'manual download'
    questions = [
        {
            'type': 'list',
            'name': name,
            'message': "ffmpeg not found would you like to auto install?",
            'choices':["Yes","No"]
        }
    ]

    answer = prompt(questions)
    return answer[name]

def continue_prompt() -> bool:
    name = 'reset username'
    questions = [
        {
            'type': 'list',
            'name': name,
            'message': "Do you want to continue with script",
            'choices':["Yes","No"]
        }
    ]

    answer = prompt(questions)
    return answer[name]
def model_selector(models,selected=None) -> bool:
    choices=list(map(lambda x:model_selectorHelper(x[0],x[1])  ,enumerate(models)))
    selectedSet=set(map(lambda x:re.search("^[0-9]+: ([^ ]+)",x["name"]).group(1),selected or []))
    for model in choices:
        name=re.search("^[0-9]+: ([^ ]+)",model.name).group(1)
        if name in selectedSet:
            model.enabled=True
    
    style=get_style({
     "questionmark": "fg:#e5c07b bg:#ffffff",
    "answermark": "#e5c07b",
    "answer": "#61afef",
    "input": "#98c379",
    "question": "",
    "answered_question": "",
    "instruction": "#abb2bf",
    "long_instruction": "#abb2bf",
    "pointer": "#61afef",
    "checkbox": "#98c379",
    "separator": "",
    "skipped": "#5c6370",
    "validator": "",
    "marker": "#e5c07b",
    "fuzzy_prompt": "#c678dd",
    "fuzzy_info": "#abb2bf",
    "fuzzy_border": "#4b5263",
    "fuzzy_match": "#c678dd bold",
    "spinner_pattern": "#e5c07b",
    "spinner_text": "",
})

    p=inquirer.fuzzy(
        long_instruction=prompt_strings.FUZZY_INSTRUCTION.format(sort=args_.getargs().sort.capitalize(),
                                                                 desc=args_.getargs().desc,
                                                                 type=(args_.getargs().account_type or "All").capitalize(),
                                                                status=(args_.getargs().sub_status or "Both").capitalize(),
                                                                renewal=(args_.getargs().renewal or "Both").capitalize()

                                                                
                                                                ),

                                                                 
        choices=choices,
        transformer=lambda result:",".join(map(lambda x:x.split(" ")[1],result)),
        multiselect=True,
        validate=prompt_validators.emptyListValidator(),
        prompt='Filter: ',
        marker="\u25c9 ",
        marker_pl="\u25cb ",
        message= "Which models do you want to scrape\n:",
        mandatory=False,
        style=style,
        keybindings=  {
                                "toggle": [{"key": "s-right"},{"key": ["pagedown","right"]},{"key": ["home","right"]}],

                                
                        }
                            
    
    )
        
    answers=p.execute()
    return answers,p
        

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
    questions = [
        {
            'type': 'list',
            'message': "Modify filters for your accounts list?\nSome usage examples are scraping free accounts only or paid accounts without renewal",
            'choices':["Yes","No"]
        }
    ]

    answer = prompt(questions)
    return answer[0]
def modify_filters_prompt(args):
    questions = [
        {
            'type': 'list',
            'message': "Filter account by whether it has a renewal date",
            'choices':[Choice("active","Active Only"),Choice("disabled","Disabled Only"),Choice(None,"Both")]
        },
        {
            'type': 'list',
            'message': "Filter accounts based on access to content via a subscription",
            'choices':[Choice("active","Active Only"),Choice("expired","Expired Only"),Choice(None,"Both")]
        },

     
            {
            'type': 'list',
            'message': "Filter accounts by the type of subscription",
            'choices':[Choice("paid","Paid Subscription Only"),Choice("free","Free Subscription Only"),Choice(None,"Both")]
        }
    ]
    answer = prompt(questions)
    args.renewal=answer[0]
    args.sub_status=answer[1]
    args.account_type=answer[2]
    return args


def decide_sort_prompt():
    questions = [
        {
            'type': 'list',
            'message': f"Change the Order or the Criteria for how the model list is sorted\nCurrent setting are {'Ascending' if not args_.getargs().desc else 'Descending'} in {args_.getargs().sort.capitalize()} order",
            'choices':["Yes","No"]
        }
    ]

    answer = prompt(questions)
    return answer[0]
def modify_sort_prompt(args):
    questions = [
        {
            'type': 'list',
            'message': "Sort Accounts by..",
            'choices':[Choice("name","By Name"),Choice("subscribed","Subscribed Date"),Choice("expired","Expiring Date"),Choice("price","Price")],
        },
        {
            'type': 'list',
            'message': "Sort Direction",
            'choices':[Choice(True,"Ascending"),Choice(False,"Descending",enabled=True)],
            "default":True

        },

    ]

    answer = prompt(questions)
    args.sort=answer[0]
    args.desc=answer[1]==False
    return args

def change_default_profile() -> bool:
    name = 'reset username'
    questions = [
        {
            'type': 'list',
            'name': name,
            'message': "Set this as the new default profile",
            'choices':["Yes","No"]
        }
    ]

    answer = prompt(questions)
    return answer[name]

def reset_config_prompt() -> bool:
    questions = [
        {
            'type': 'list',
            'message': "How do you want to fix this issue",
            'choices':["Reset Default","Manually Edit Config"]
        }
    ]

    answer = prompt(questions)
    return answer[0]

def manual_config_prompt(configText) -> str:
    
    
    questions = [
        
     
        
        
        {
               "keybindings":{
                             "answer": [{"key": ["pagedown","enter"]},{"key": ["home","enter"]}],

                              
                         },
            'type': 'input',
            'multiline':True,
            'default':configText,
            'message': "Edit config text",
            "instruction":"\nKeyBindings\nSubmit: esc+Enter or Home+Enter or pageDown +Enter",
        }
    ]


    answer = prompt(questions)
    return answer[0]
def manual_auth_prompt(authText) -> str:
    
    
    questions = [
        
     
        
        
        {
               "keybindings":{
                             "answer": [{"key": ["pagedown","enter"]},{"key": ["home","enter"]}],

                              
                         },
            'type': 'input',
            'multiline':True,
            'default':authText,
            'message': "Edit auth text",
            "instruction":"\nKeyBindings\nSubmit: esc+Enter or Home+Enter or pageDown +Enter",
        }
    ]


    answer = prompt(questions)
    return answer[0]

def relative_config_path_prompt(curr,file) -> bool:
    name = 'path'
    questions = [
        {
            'type': 'list',
            'name': name,
            'message': "Where do you want to make the config folder",
            'choices':[Choice(True,str(pathlib.Path(curr,file))),Choice(False,str(pathlib.Path(file)))]
        }
    ]

    answer = prompt(questions)
    return answer[name]