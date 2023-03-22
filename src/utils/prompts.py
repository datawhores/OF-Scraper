r"""
               _          __                                                                      
  ___   _ __  | | _   _  / _|  __ _  _ __   ___         ___   ___  _ __   __ _  _ __    ___  _ __ 
 / _ \ | '_ \ | || | | || |_  / _` || '_ \ / __| _____ / __| / __|| '__| / _` || '_ \  / _ \| '__|
| (_) || | | || || |_| ||  _|| (_| || | | |\__ \|_____|\__ \| (__ | |   | (_| || |_) ||  __/| |   
 \___/ |_| |_||_| \__, ||_|   \__,_||_| |_||___/       |___/ \___||_|    \__,_|| .__/  \___||_|   
                  |___/                                                        |_|                
"""

import re


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
            'choices': [
                Choice('All', enabled=True),
                Choice('Timeline'),
                Choice('Archived'),
                Choice('Highlights'),
                Choice('Messages'),
            ]
        }
    ]

    while True:
        answers = prompt(questions)
        if not answers[name]:
            print('Error: You must select at least one.')
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
            'name': 'app-token',
            'message': 'Enter your `app-token` value:',
            'default': auth['app-token']
        },
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
            print('You must type a name. Try again.')

        if re.search(pattern, answer[name]):
            print('Profile name contains invalid characters. Try again.')
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
            print(profile)
            print(profiles)
            print('That profile does not exist.')
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
            'type': 'confirm',
            'name': name,
            'message': "Do you want to reset username option",
        }
    ]

    answer = prompt(questions)
    return answer[name]
def model_selector(models) -> bool:
    questions = [
    {"type": "checkbox", "message": "Which models do you want to scrape:"
      ,"validate":(lambda result: len(result)> 0),
      "invalid_message":"Input cannot be empty","instruction":"\nPress Ctrl -R toggles all choices\nSpace Bar toggles a single choice\nPress Enter When Done","choices":list(map(lambda x:Choice(x[0],name=f"{x[0]} {x[2]}"),sorted(models,key=lambda x:x[0])))}
]

    return prompt(questions)[0]


