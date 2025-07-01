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
import ofscraper.utils.system.free as free
import ofscraper.utils.settings as settings


def reset_download():
    args = settings.get_args()

    if bool(args.download_area) and prompts.reset_download_areas_prompt() == "Yes":
        args.scrape_paid = None
        args.download_area = {}


def reset_like():
    args = settings.get_args()
    if bool(args.like_area) and prompts.reset_like_areas_prompt() == "Yes":
        args.like_area = {}


@free.space_checker
def select_areas(actions=None, reset=False):
    args = settings.get_args()
    actions = actions or args.action or {}
    if "download" in actions and reset:
        reset_download()
    elif ("like" or "unlike") in actions and reset:
        reset_like()
    settings.update_args(args)
    set_post_area(actions)
    set_download_area(actions)
    set_like_area(actions)
    remove_post_area()


def remove_like_area():
    args = settings.get_args()
    args.like_area = {}
    settings.update_args(args)


def remove_download_area():
    args = settings.get_args()
    args.download_area = {}
    args.scrape_paid = None
    settings.update_args(args)


def remove_post_area():
    args = settings.get_args()
    args.posts = {}
    settings.update_args(args)


@free.space_checker
# set post for primarily for download-area, secondary for like/unlike
def set_post_area(action=None):
    args = settings.get_args()
    action = action or args.action or {}
    if "download" not in action:
        return
    if areas.get_text_area():
        return
    elif settings.get_settings().command == "metadata":
        return
    elif len(areas.get_download_area()) > 0:
        return
    elif len(areas.get_like_area()) > 0:
        return
    elif len(args.posts) > 0:
        return
    args.posts = prompts.areas_prompt()
    settings.update_args(args)


# set download area area based primarly on posts,secondary on  prompt
def set_download_area(action=None):
    args = settings.get_args()
    action = action or args.action or {}
    selected = None
    not_anon_safe = ["Messages", "Purchases", "Highlights", "Stories"]
    selected = areas.get_download_area()
    if areas.get_text_area():
        pass
    elif settings.get_settings().command == "metadata":
        if args.anon and all([ele in not_anon_safe for ele in selected]):
            selected = prompts.metadata_anon_areas_prompt()
        elif not args.anon and len(selected) == 0:
            selected = prompts.metadata_areas_prompt()
    elif len(selected) == 0 and settings.get_settings().command == "db":
        selected = prompts.db_areas_prompt()
    elif len(selected) == 0 and "download" in action:
        selected = prompts.download_areas_prompt()
    args.download_area = selected
    settings.update_args(args)


# set like area based primarly on posts,secondary on from prompt
def set_like_area(action=None):
    args = settings.get_args()
    action = action or args.action or {}
    if "like" not in action and "unlike" not in action:
        return
    args.like_area = (
        areas.get_like_area()
        if len(areas.get_like_area()) > 0
        else prompts.like_areas_prompt()
    )
    settings.update_args(args)


def set_scrape_paid(action=None):
    args = settings.get_args()
    action = action or args.action or {}
    if "download" not in action:
        return
    args.scrape_paid = (
        prompts.scrape_paid_prompt() if not args.scrape_paid else args.scrape_paid
    )
    settings.update_args(args)
