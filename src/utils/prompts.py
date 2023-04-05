r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import re
import json
import sys
from rich.console import Console
console=Console()
from InquirerPy.resolver import prompt
from InquirerPy.separator import Separator
from InquirerPy.base import Choice

from ..constants import mainPromptChoices, usernameOrListChoices, profilesPromptChoices


def main_prompt() -> int:
    main_prompt_choices = [*mainPromptChoices]
    main_prompt_choices.insert(4, Separator())

    name = 'action'

    questions = [
        {
            'type': 'list',
            'name': name,
            'message': 'What would you like to do?',
            'choices': [*main_prompt_choices]
        }
    ]

    answer = prompt(questions)
    return mainPromptChoices[answer[name]]


def username_or_list_prompt() -> int:
    name = 'username_or_list'

    questions = [
        {
            'type': 'list',
            'name': name,
            'message': 'Choose one of the following options:',
            'choices': [*usernameOrListChoices]
        }
    ]

    answer = prompt(questions)
    return usernameOrListChoices[answer[name]]


def verify_all_users_username_or_list_prompt() -> bool:
    name = 'all_users'

    questions = [
        {
            'type': 'confirm',
            'name': name,
            'message': 'Are you sure you want to scrape every model that you\'re subscribed to?',
            'default': False
        }
    ]

    answer = prompt(questions)
    return answer[name]


def username_prompt() -> str:
    name = 'username'

    questions = [
        {
            'type': 'input',
            'name': name,
            'message': 'Enter a comma seperated list of model\'s usernames:'
        }
    ]

    answer = prompt(questions)
    return answer[name]


def areas_prompt() -> list:
    name = 'areas'

    questions = [
        {
            'type': 'checkbox',
            'qmark': '[?]',
            'name': name,
            'message': 'Which area(s) would you like to scrape? (Press ENTER to continue)',
             "validate":(lambda result: len(result)> 0),
      "invalid_message":"Input cannot be empty",
            'choices': [
                Choice('Timeline'),
                Choice('Archived'),
                Choice('Highlights'),
                Choice('Stories'),
                Choice('Messages'),
            ]
            ,"instruction":"\nPress Ctrl -R toggles all choices\nSpace toggles a single choice\nPress enter when done",

        }
    ]

    while True:
        answers = prompt(questions)
        if not answers[name]:
            console.print('Error: You must select at least one.')
        break
    return answers[name]


def database_prompt() -> tuple:
    name1 = 'path'
    name2 = 'username'

    questions = [
        {
            'type': 'input',
            'name': name1,
            'message': 'Enter the path to the directory that contains your database files:'
        },
        {
            'type': 'input',
            'name': name2,
            'message': 'Enter that model\'s username:'
        }
    ]

    answers = prompt(questions)
    return (answers[name1], answers[name2])


def auth_prompt(auth) -> dict:
    questions = [
        {
            'type': 'input',
            'name': 'sess',
            'message': 'Enter your `sess` cookie:',
            'default': auth['sess']
        },
        {
            'type': 'input',
            'name': 'auth_id',
            'message': 'Enter your `auth_id` cookie:',
            'default': auth['auth_id']
        },
        {
            'type': 'input',
            'name': 'auth_uid_',
            'message': 'Enter your `auth_uid_` cookie (leave blank if you don\'t use 2FA):',
            'default': auth['auth_uid_']
        },
        {
            'type': 'input',
            'name': 'user_agent',
            'message': 'Enter your `user agent`:',
            'default': auth['user_agent']
        },
        {
            'type': 'input',
            'name': 'x-bc',
            'message': 'Enter your `x-bc` token:',
            'default': auth['x-bc']
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
            'message': "It doesn't seem you have an `auth.json` file. Would you like to make one?",
        }
    ]

    answer = prompt(questions)
    return answer[name]

def browser_prompt()->str:
    pythonver=float(f"{sys.version_info[0]}.{sys.version_info[1]}")
    msg="Select how to retrive auth information"

    if pythonver<3.9 or pythonver>=3.11:
        console.print("\nNote: Browser Extractions only works with default Profile\n\n")
        questions = [
            {
                'type': 'list',
                'message':msg ,
                'choices':["Enter Each Field Manually","Paste From Cookie Helper", Separator(line="-----------\nBrowser Extractions"),"Chrome","Chromium","Firefox","Opera","Opera GX","Edge","Chromium","Brave","Vivaldi","Safari"],
                "default":"Enter Each Field Manually"

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
def user_agent_prompt(current,new=None):
    new =new or "Unknown Please Ignore"

    questions = [
        {
            'type': 'input',
            'message':'Enter User_Agent from browser',
            'default':current
        }
    ]
    return  prompt(questions)[0].strip()

def xbc_prompt():
    questions = [
        {
            'type': 'input',
            'message':'Enter x-bc request header',
            'instruction':f"\nGo to browser network tools to view\nFor more instructions visit https://github.com/excludedBittern8/ofscraper\n\n"
        }
    ]
    return  prompt(questions)[0].strip()




def auth_full_paste():
    questions = [
        {
            'type': 'input',
            'message':'Paste Text from Extension',
            "filter": lambda result: json.loads(result),
             "instruction":"\n\nCookie Helper Repo:https://github.com/M-rcus/OnlyFans-Cookie-Helper/\n\n"

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
            'choices': [*profilesPromptChoices]
        }
    ]

    answer = prompt(questions)
    return profilesPromptChoices[answer[name]]


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
            'message': f'What would you like to rename {old_profile_name} to?'
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
            'message': 'What would you like to name your new profile? [ONLY letters, numbers, and underscores!]'
        }
    ]

    while True:
        pattern = re.compile(r'[^\w+^\d+^_+]')
        answer = prompt(questions)

        if not answer[name]:
            console.print('You must type a name. Try again.')

        if re.search(pattern, answer[name]):
            console.print('Profile name contains invalid characters. Try again.')
        break

    return answer[name]


def get_profile_prompt(profiles: list) -> str:
    name = 'get_profile'

    questions = [
        {
            'type': 'input',
            'name': name,
            'message': 'Enter a profile:'
        }
    ]

    while True:
        answer = prompt(questions)
        profile = answer[name]

        if profile not in profiles:
            console.print(profile)
            console.print(profiles)
            console.print('That profile does not exist.')
        else:
            break

    return profile


def config_prompt(config) -> dict:
    questions = [
        {
            'type': 'input',
            'name': 'main_profile',
            'message': 'What would you like your main profile to be?',
            'default': config['main_profile']
        },
        {
            'type': 'input',
            'name': 'save_location',
            'message': 'Where would you like to save downloaded content?',
            'default': config.get('save_location', '')
        },
        {
            'type': 'input',
            'name': 'file_size_limit',
            'message': 'File size limit (enter a value in bytes):',
            'default': config.get('file_size_limit', '')
        }
    ]

    answers = prompt(questions)
    answers.update({'save_location': answers.get(
        'save_location').strip('\"')})
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
def model_selector(models) -> bool:
    questions = [
    {"type": "fuzzy", "message": "Which models do you want to scrape:",
      "keybindings":{
                             "toggle": [{"key": "s-right"}],
                         }
     ,"multiselect":True
      ,"validate":(lambda result: len(result)> 0),
      "invalid_message":"Input cannot be empty",
      "instruction":"\nPress Ctrl -R toggles all choices\nShift+Right arrow toggles a single choice\nPress Enter When Done\n\nParantheses indicates number of selected users\n\nValues: Name Renewal_Date/Expired_Date Active_Subscription","choices":list(map(lambda x:Choice(x,name=f"{x['name']} {x['date'] } {x['active']}")   ,sorted(models,key=lambda x:x['name']))),"transformer":lambda result:",".join(map(lambda x:x.split(" ")[0],result))
       ,"prompt":'Filter: ',
       "marker":"\u25c9 ",
       "marker_pl":"\u25cb "

      },
    
]

    return prompt(questions)[0]


def download_paid_prompt() -> bool:
    questions = [
        {
            'type': 'list',
            'message': "Would you like to also download paid content",
            'choices':["Yes","No"]
        }
    ]

    answer = prompt(questions)
    return answer[0]

def decide_filters_prompts():
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
            'message': "Filter account by renewal of subscription status",
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
            'choices':[Choice("paid","Paid Only"),Choice("free","Free Only"),Choice(None,"Both")]
        }
    ]
    answer = prompt(questions)
    args.renewal=answer[0]
    args.sub_status=answer[1]
    args.account_type=answer[2]
    return args
 