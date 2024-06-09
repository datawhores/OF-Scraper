import logging
import shutil

from rich import print

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args
import ofscraper.utils.config.config as config_
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.paths.manage as manage
import ofscraper.utils.profiles.data as profile_data
import ofscraper.utils.profiles.tools as tools

log = logging.getLogger("shared")
console = console.shared_console
currentData = None
currentProfile = None


def change_profile():
    tools.print_profiles()
    profile = prompts.get_profile_prompt(profile_data.get_profile_names())
    config_.update_config(constants.getattr("mainProfile"), profile)
    args = read_args.retriveArgs()
    # remove profile argument
    args.profile = None
    write_args.setArgs(args)
    print(f"[green]Successfully changed profile to[/green] {profile}")


def delete_profile():
    tools.print_profiles()
    profile = prompts.get_profile_prompt(profile_data.get_profile_names())
    p = common_paths.get_config_home() / profile
    shutil.rmtree(p)

    print(f"[green]Successfully deleted[/green] {profile}")


def create_profile():
    tools.print_profiles()
    name = tools.profile_name_fixer(prompts.create_profiles_prompt())
    manage.create_profile_path(name)
    if prompts.change_default_profile() == "Yes":
        config_.update_config(constants.getattr("mainProfile"), name)
    console.print(
        "[green]Successfully created[/green] {dir_name}".format(dir_name=name)
    )


def edit_profile_name():
    tools.print_profiles()
    profiles_ = profile_data.get_profiles()
    old_profile_name = prompts.edit_profiles_prompt(profiles_)
    new_profile_name = tools.profile_name_fixer(
        prompts.new_name_edit_profiles_prompt(old_profile_name)
    )
    configFolder = common_paths.get_config_home()
    oldFolder = configFolder / old_profile_name
    newFolder = configFolder / new_profile_name

    if not oldFolder.exists():
        manage.create_profile_path(new_profile_name)
    else:
        shutil.move(oldFolder, newFolder)
        change_current_profile(new_profile_name, old_profile_name)
        print(
            f"[green]Successfully changed[green] '{old_profile_name}' to '{new_profile_name}'"
        )


def change_current_profile(new_profile, old_profile):
    args = read_args.retriveArgs()
    if args.profile == old_profile:
        args.profile = new_profile
        write_args.setArgs(args)
    # required because name has changed
    if old_profile == profile_data.get_current_config_profile():
        config_.update_config(constants.getattr("mainProfile"), new_profile)
