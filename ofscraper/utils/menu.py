import logging
from contextlib import contextmanager

import ofscraper.actions.process as process_actions
import ofscraper.models.selector as userselector
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.actions as actions
import ofscraper.utils.auth as auth
import ofscraper.utils.checkers as checkers
import ofscraper.utils.config.menu as config_menu
import ofscraper.utils.profiles.manage as profiles_manage
import ofscraper.utils.profiles.tools as profile_tools
import ofscraper.utils.run as run

log = logging.getLogger("shared")
count = 0


def update_count():
    global count
    count = count + 1


def get_count():
    global count
    return count


def main_menu_action():
    global count
    log.debug(f"[bold blue] Running Prompt Menu Mode[/bold blue]")
    while True:
        result_main_prompt = prompts.main_prompt()
        if result_main_prompt == "action":
            action_result_prompt = prompts.action_prompt()
            if action_result_prompt == "quit":
                return True
            elif action_result_prompt == "main":
                continue
            else:
                checkers.check_config()
                count > 0 and reset_menu_helper()
                functs = process_actions.add_selected_areas()
                run.run_helper(*functs)
                count = count + 1
        elif result_main_prompt == "auth":
            # Edit `auth.json` file
            auth_result_prompt = auth.edit_auth()
            if auth_result_prompt == "quit":
                return True
        elif result_main_prompt == "config":
            # Edit `data.json` file
            while True:
                config_result_prompt = prompts.config_prompt()
                if config_result_prompt == "quit":
                    return True
                elif config_result_prompt == "main":
                    break
                else:
                    config_menu_helper(config_result_prompt)

        elif result_main_prompt == "profile":
            # Display  `Profiles` menu
            while True:
                result_profiles_prompt = prompts.profiles_prompt()
                if result_profiles_prompt == "quit":
                    return True
                elif result_profiles_prompt == "main":
                    break
                else:
                    profile_menu_helper(result_profiles_prompt)
        elif result_main_prompt == "quit":
            return True


def profile_menu_helper(result_profiles_prompt):
    if result_profiles_prompt == "default":
        # Change profiles
        profiles_manage.change_profile()

    elif result_profiles_prompt == "name":
        # Edit a profile
        profiles_manage.edit_profile_name()

    elif result_profiles_prompt == "create":
        # Create a new profile

        profiles_manage.create_profile()

    elif result_profiles_prompt == "delete":
        # Delete a profile
        profiles_manage.delete_profile()

    elif result_profiles_prompt == "view":
        # View profiles
        profile_tools.print_profiles()


def config_menu_helper(result_config_prompt):
    if result_config_prompt == "download":
        config_menu.download_config()
    elif result_config_prompt == "file":
        config_menu.file_config()
    elif result_config_prompt == "general":
        config_menu.general_config()
    elif result_config_prompt == "binary":
        config_menu.binary_config()
    elif result_config_prompt == "cdm":
        config_menu.cdm_config()
    elif result_config_prompt == "performance":
        config_menu.performance_config()
    elif result_config_prompt == "advanced":
        config_menu.advanced_config()
    elif result_config_prompt == "response":
        config_menu.response_type()


def reset_menu_helper():
    reset = prompts.reset_areas_prompt()
    if reset == "Both":
        actions.remove_download_area()
        actions.remove_like_area()
    elif reset == "Download":
        actions.remove_download_area()
    elif reset == "Like":
        actions.remove_like_area()
    userselector.getselected_usernames(reset=True)
