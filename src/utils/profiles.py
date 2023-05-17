r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import pathlib
import shutil
from rich.console import Console
from rich import print
import src.utils.config as config_
import src.prompts.prompts as prompts
import src.constants as constants

console=Console()


def get_profile_path():
    config_path = pathlib.Path.home() / constants.configPath
    return config_path


def get_profiles() -> list:
    config_path = get_profile_path()
    dir_contents = config_path.glob('*')
    profiles = [item for item in dir_contents if item.is_dir()]
    return profiles

def change_profile():
    console.print('Current profiles:')
    profile = prompts.get_profile_prompt(print_profiles())

    config_.update_config(constants.mainProfile, profile)

    print(f'[green]Successfully changed profile to[/green] {profile}')


def delete_profile():
    console.print('Current profiles:')
    profile = prompts.get_profile_prompt(print_profiles())

    if profile == get_current_profile():
        raise OSError(
            'You cannot delete a profile that you\'re currently using')

    p = get_profile_path() / profile
    shutil.rmtree(p)

    print(f'[green]Successfully deleted[/green] {profile}')


def create_profile(path, dir_name: str):
    dir_path = path / dir_name

    if not dir_path.is_dir():
        dir_path.mkdir(parents=True, exist_ok=False)
    if prompts.change_default_profile()=="Yes":
        config_.update_config(constants.mainProfile, dir_name)
    console.print('[green]Successfully created[/green] {dir_name}'.format(dir_name=dir_name))
    

def edit_profile_name(old_profile_name: str, new_profile_name: str):
    profiles = get_profiles()

    for profile in profiles:
        if profile.stem == old_profile_name:
            profile.replace(profile.parent / new_profile_name)
            shutil.rmtree(profile,ignore_errors=True)
           
    if old_profile_name == get_current_profile():
        config_.update_config(constants.mainProfile, new_profile_name)

    print(
        f"[green]Successfully changed[green] '{old_profile_name}' to '{new_profile_name}'")


def print_profiles() -> list:
    profile_names = [profile.stem for profile in get_profiles()]

    profile_fmt = 'Profile: [cyan]{}'
    for name in profile_names:
        console.print(profile_fmt.format(name))

    return profile_names


def get_current_profile():
    config = config_.read_config()
    return config[constants.mainProfile]


def print_current_profile():
    get_profiles()

    current_profile = get_current_profile()
    print('Using profile: [cyan]{}[/cyan]'.format(current_profile))
