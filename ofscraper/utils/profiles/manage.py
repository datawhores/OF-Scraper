import logging

from rich import print

import ofscraper.db.postgres as postgres
import ofscraper.managers.manager as manager
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.console as console
import ofscraper.utils.paths.manage as manage
import ofscraper.utils.profiles.data as profile_data
import ofscraper.utils.profiles.tools as tools
from ofscraper.utils.markup import escape_text

log = logging.getLogger("shared")


def change_default_profile():
    tools.print_profiles()
    profile = prompts.get_profile_prompt(profile_data.get_profile_names())
    manager.Manager.profile_manager.switch_profile(profile,permanent=True)
    postgres_profiles_notice()


def change_active_profile():
    tools.print_profiles()
    profile = prompts.get_profile_prompt(profile_data.get_profile_names())
    manager.Manager.profile_manager.switch_profile(profile,permanent=False)
    postgres_profiles_notice()


def postgres_profiles_notice():
    # PostgreSQL's tables are per site, not per profile
    if postgres.enabled():
        console.get_console().print(
            "All profiles use the same PostgreSQL database, so switching"
            " profiles doesn't switch the scraper's data."
        )


def delete_profile():
    tools.print_profiles()
    profile = prompts.get_profile_prompt(profile_data.get_profile_names())
    if profile==profile_data.get_active_profile():
        log.error("can't delete active profile")
        return
    # removes the folder and the creator lists kept for the profile
    manager.Manager.profile_manager.delete_profile(profile)
    print(f"[green]Successfully deleted[/green] {escape_text(profile)}")


def create_profile():
    tools.print_profiles()
    name = tools.profile_name_fixer(prompts.create_profiles_prompt())
    choice=prompts.change_selected_profile()
    manage.create_profile_path(name)
    if choice=="default":
        manager.Manager.profile_manager.switch_profile(name,permanent=True)
    if choice=="active":
        manager.Manager.profile_manager.switch_profile(name,permanent=False)
    # the answer to a prompt, so shown even when --output quiets the shared console
    console.get_console().print(
        "[green]Successfully created[/green] {dir_name}".format(dir_name=escape_text(name))
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
