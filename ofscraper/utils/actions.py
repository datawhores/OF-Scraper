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

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args.accessors.areas as areas
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args
import ofscraper.utils.system.free as free
from ofscraper.utils.args.accessors.command import get_command



def reset_download():
    args = read_args.retriveArgs()

    if bool(args.download_area) and prompts.reset_download_areas_prompt() == "Yes":
        args.scrape_paid = None
        args.download_area = {}


def reset_like():
    args = read_args.retriveArgs()
    if bool(args.like_area) and prompts.reset_like_areas_prompt() == "Yes":
        args.like_area = {}


@free.space_checker
def select_areas(action=None, reset=False):
    args = read_args.retriveArgs()
    action = action or args.action or {}
    if "download" in action and reset:
        reset_download()
    elif ("like" or "unlike") in action and reset:
        reset_like()
    write_args.setArgs(args)
    set_post_area(action)
    set_download_area(action)
    set_like_area(action)
    remove_post_area()


def remove_like_area():
    args = read_args.retriveArgs()
    args.like_area = {}
    write_args.setArgs(args)


def remove_download_area():
    args = read_args.retriveArgs()
    args.download_area = {}
    args.scrape_paid = None
    write_args.setArgs(args)


def remove_post_area():
    args = read_args.retriveArgs()
    args.posts = {}
    write_args.setArgs(args)


@free.space_checker
# set post for primarily for download-area, secondary for like/unlike
def set_post_area(action=None):
    args = read_args.retriveArgs()
    action = action or args.action or {}
    if "download" not in action:
        return
    if areas.get_text_area():
        return
    elif get_command()== "metadata":
        return
    elif len(areas.get_download_area()) > 0:
        return
    elif len(areas.get_like_area()) > 0:
        return
    elif len(args.posts) > 0:
        return
    args.posts = prompts.areas_prompt()
    write_args.setArgs(args)


# set download area area based primarly on posts,secondary on  prompt
def set_download_area(action=None):
    args = read_args.retriveArgs()
    action = action or args.action or {}
    selected = None
    not_anon_safe = ["Messages", "Purchases", "Highlights", "Stories"]
    selected = areas.get_download_area()
    if areas.get_text_area():
        pass
    elif get_command() == "metadata":
        if args.anon and all([ele in not_anon_safe for ele in selected]):
            selected = prompts.metadata_anon_areas_prompt()
        elif not args.anon and len(selected) == 0:
            selected = prompts.metadata_areas_prompt()
    elif len(selected) == 0 and get_command() == "db":
        selected = prompts.db_areas_prompt()
    elif len(selected) == 0 and "download" in action:
        selected = prompts.download_areas_prompt()
    args.download_area = selected
    write_args.setArgs(args)


# set like area based primarly on posts,secondary on from prompt
def set_like_area(action=None):
    args = read_args.retriveArgs()
    action = action or args.action or {}
    if "like" not in action and "unlike" not in action:
        return
    args.like_area = (
        areas.get_like_area()
        if len(areas.get_like_area()) > 0
        else prompts.like_areas_prompt()
    )
    write_args.setArgs(args)


def set_scrape_paid(action=None):
    args = read_args.retriveArgs()
    action = action or args.action or {}
    if "download" not in action:
        return
    args.scrape_paid = (
        prompts.scrape_paid_prompt() if not args.scrape_paid else args.scrape_paid
    )
    write_args.setArgs(args)
