r"""
               _          __
  ___   _ __  | | _   _  / _|  __ _  _ __   ___         ___   ___  _ __   __ _  _ __    ___  _ __
 / _ \ | '_ \ | || | | || |_  / _` || '_ \ / __| _____ / __| / __|| '__| / _` || '_ \  / _ \| '__|
| (_) || | | || || |_| ||  _|| (_| || | | |\__ \|_____|\__ \| (__ | |   | (_| || |_) ||  __/| |
 \___/ |_| |_||_| \__, ||_|   \__,_||_| |_||___/       |___/ \___||_|    \__,_|| .__/  \___||_|
                  |___/                                                        |_|
"""

import pathlib
import shutil
from rich.console import Console
from rich import print
console=Console()
from .config import read_config, update_config
from .prompts import get_profile_prompt
from ..constants import configPath, configFile, mainProfile
configPath = '.config/ofscraper'


def get_profile_path():
    config_path = pathlib.Path.home() / configPath
    return config_path


def get_profiles() -> list:
    config_path = get_profile_path()

    # (This block of code should be removed in the 1.0 release)
    #
    # If user upgraded from an older version of ofscraper or if the user
    # has an auth.json or models.db file in the config_path:
    # if has_files(config_path):
    #     create_profile(config_path, mainProfile)
    #     move_files(config_path, mainProfile)

    # If not, continue as usual:
    dir_contents = config_path.glob('*')
    profiles = [item for item in dir_contents if item.is_dir()]
    return profiles


def has_files(path) -> bool:
    files = path.glob('*.*')

    filtered_files = filter_files(files)

    if filtered_files:
        return True
    return False


def filter_files(files) -> list:
    # Check for `config.json` file:
    filtered_files = [file for file in files if file.name != configFile]
    return filtered_files


def move_files(path, dir_name: str):
    files = path.glob('*.*')
    filtered_files = filter_files(files)

    for file in filtered_files:
        file.rename(file.parent / dir_name / file.name)


def change_profile():
    console.print('Current profiles:')
    profile = get_profile_prompt(print_profiles())

    update_config(mainProfile, profile)

    print(f'\033[32mSuccessfully changed profile to\033[0m {profile}')


def delete_profile():
    console.print('Current profiles:')
    profile = get_profile_prompt(print_profiles())

    if profile == get_current_profile():
        raise OSError(
            'You cannot delete a profile that you\'re currently using')

    p = get_profile_path() / profile
    shutil.rmtree(p)

    print(f'\033[32mSuccessfully deleted\033[0m {profile}')


def create_profile(path, dir_name: str):
    dir_path = path / dir_name

    if not dir_path.is_dir():
        dir_path.mkdir(parents=True, exist_ok=False)
        pathlib()
    

    print(f'\033[32mSuccessfully created\033[0m {dir_name}')


def edit_profile_name(old_profile_name: str, new_profile_name: str):
    profiles = get_profiles()

    for profile in profiles:
        if profile.stem == old_profile_name:
            profile.rename(profile.parent / new_profile_name)

    print(
        f"\033[32mSuccessfully changed\033[0m '{old_profile_name}' \033[32mto\033[0m '{new_profile_name}'")


def print_profiles() -> list:
    profile_names = [profile.stem for profile in get_profiles()]

    profile_fmt = 'Profile: \033[36m{}\033[0m'
    for name in profile_names:
        print(profile_fmt.format(name))

    return profile_names


def get_current_profile():
    config = read_config()
    return config['config'][mainProfile]


def print_current_profile():
    get_profiles()

    current_profile = get_current_profile()
    print('Using profile: [cyan]{}[/cyan]'.format(current_profile))
