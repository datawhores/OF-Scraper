import logging
import shutil

from rich import print

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.console as console
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.paths.manage as manage
import ofscraper.utils.profiles.data as profile_data
import ofscraper.utils.profiles.tools as tools
import ofscraper.managers.manager as manager


log = logging.getLogger("shared")
console = console.shared_console
currentData = None
currentProfile = None


def change_default_profile():
    tools.print_profiles()
    profile = prompts.get_profile_prompt(profile_data.get_profile_names())
    manager.Manager.profile_manager.switch_profile(profile,permanent=True)


def change_active_profile():
    tools.print_profiles()
    profile = prompts.get_profile_prompt(profile_data.get_profile_names())
    manager.Manager.profile_manager.switch_profile(profile,permanent=False)
def delete_profile():
    tools.print_profiles()
    profile = prompts.get_profile_prompt(profile_data.get_profile_names())
    if profile==profile_data.get_active_profile():
        log.error("can't delete active profile")
        return
    p = common_paths.get_config_home() / profile
    shutil.rmtree(p)
    manager.Manager.profile_manager.delete_profile()
    print(f"[green]Successfully deleted[/green] {profile}")


def create_profile():
    tools.print_profiles()
    name = tools.profile_name_fixer(prompts.create_profiles_prompt())
    manage.create_profile_path(name)
    choice=prompts.change_selected_profile()
    if choice=="default":
        manager.Manager.profile_manager.switch_profile(name,permanent=True)
    if choice=="active":
        manager.Manager.profile_manager.switch_profile(name,permanent=False)
    console.print(
        "[green]Successfully created[/green] {dir_name}".format(dir_name=name)
    )

def edit_profile_name():
    """
    Handles the user prompts for renaming a profile and calls the manager
    to perform the action.
    """
    # --- 1. Get User Input ---
    tools.print_profiles()
    profiles_ = profile_data.get_profiles()
    old_profile_name = prompts.edit_profiles_prompt(profiles_)

    # Exit if user cancels
    if not old_profile_name:
        return

    new_profile_name = tools.profile_name_fixer(
        prompts.new_name_edit_profiles_prompt(old_profile_name)
    )
    # Exit if user cancels
    if not new_profile_name:
        return
    manager.Manager.profile_manager.rename_profile(old_profile_name, new_profile_name)
