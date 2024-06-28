r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import logging
import re

from rich.console import Console

import ofscraper.utils.profiles.data as profile_data

log = logging.getLogger("shared")
console = Console()
currentData = None
currentProfile = None


def print_profiles() -> list:
    print_current_profile()
    console.print("\n\nCurrent Profiles\n")
    profile_fmt = "Profile: [cyan]{}"
    for name in profile_data.get_profile_names():
        console.print(profile_fmt.format(name))


def print_current_profile():
    current_profile = profile_data.get_active_profile()
    log.info("Using profile: [cyan]{}[/cyan]".format(current_profile))


def profile_name_fixer(input):
    input = str(input)
    return f"{re.sub('_profile','', input)}_profile" if input else None
