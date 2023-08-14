r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import shutil
import re
import logging
from rich.console import Console
from rich import print
import ofscraper.utils.config as config_
import ofscraper.prompts.prompts as prompts
import ofscraper.constants as constants
import ofscraper.utils.paths as paths_
import ofscraper.utils.args as args_


log=logging.getLogger("shared")
console=Console()
currentData=None
currentProfile=None

       

def get_my_info():
    global currentData
    global currentProfile
    if currentProfile==get_active_profile():
        return currentData
    else:
        import ofscraper.utils.auth as auth_
        import ofscraper.api.me as me
        currentProfile=get_active_profile()
        currentData= me.scrape_user()
    return currentData




def create_profile_path(name=None):
    out=paths_.get_profile_path(name)
    out.mkdir(exist_ok=True,parents=True)
    return out


def get_profiles() -> list:
    config_path = paths_.get_config_home()
    return list(filter(lambda x:re.search(".*_profile$",str(x)) and x.is_dir(),config_path.glob('*')))

def change_profile():
    print_profiles()
    profile = prompts.get_profile_prompt(get_profile_names())
    config_.update_config(constants.mainProfile, profile)
    args=args_.getargs()
    # remove profile argument
    args.profile=None
    args_.changeargs(args)
    print(f'[green]Successfully changed profile to[/green] {profile}')


def delete_profile():
    print_profiles()
    profile = prompts.get_profile_prompt(get_profile_names())
    p = paths_.get_config_home() / profile
    shutil.rmtree(p)

    print(f'[green]Successfully deleted[/green] {profile}')


def create_profile():
    print_profiles()
    name=profile_name_fixer( prompts.create_profiles_prompt())
    create_profile_path(name)
    if prompts.change_default_profile()=="Yes":
        config_.update_config(constants.mainProfile,name )
    console.print('[green]Successfully created[/green] {dir_name}'.format(dir_name=name))




def edit_profile_name():
    print_profiles()
    profiles_ = get_profiles()
    old_profile_name = prompts.edit_profiles_prompt(profiles_)
    new_profile_name=profile_name_fixer(prompts.new_name_edit_profiles_prompt(old_profile_name))
    configFolder=paths_.get_config_home()
    oldFolder=configFolder/old_profile_name
    newFolder=configFolder/new_profile_name    

    if not oldFolder.exists():
        create_profile_path(new_profile_name)
    else:
        shutil.move(oldFolder,newFolder)
        change_current_profile(new_profile_name,old_profile_name)
        print(
            f"[green]Successfully changed[green] '{old_profile_name}' to '{new_profile_name}'")



def change_current_profile(new_profile,old_profile):
    args=args_.getargs()
    if args.profile==old_profile:
        args.profile=new_profile
        args_.changeargs(args)
    # required because name has changed
    if old_profile== get_current_config_profile():
        config_.update_config(constants.mainProfile, new_profile)

  
def print_profiles() -> list:
    print_current_profile()
    console.print("\n\nCurrent Profiles\n")
    profile_fmt = 'Profile: [cyan]{}'
    for name in  get_profile_names():
        console.print(profile_fmt.format(name))


def get_profile_names():
    return [profile.name for profile in get_profiles()]

    
def get_current_config_profile():
    return config_.get_main_profile(config_.read_config())
    

def get_active_profile():
    if args_.getargs().profile:
        return args_.getargs().profile
    return get_current_config_profile()

def print_current_profile():
    current_profile = get_active_profile()
    log.info('Using profile: [cyan]{}[/cyan]'.format(current_profile))

def profile_name_fixer(input):
    return f"{re.sub('_profile','', input)}_profile" if input else None
