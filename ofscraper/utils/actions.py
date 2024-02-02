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
import ofscraper.utils.args.areas as areas
import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.system.free as free


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
    action = action or args.action
    if "download" in action and reset:
        reset_download()
    elif ("like" or "unlike") in action and reset:
        reset_like()
    write_args.setArgs(args)
    set_post_area(action)
    set_download_area(action)
    set_scrape_paid(action)
    set_like_area(action)
    remove_post_area()


def remove_like_area():
    args = read_args.retriveArgs()
    args.like_area = {}
    write_args.setArgs(args)


def remove_download_area():
    args = read_args.retriveArgs()
    args.download_area = {}
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
    elif len(areas.get_download_area()) > 0:
        return
    elif len(args.posts) > 0:
        return
    args.posts = prompts.areas_prompt()
    write_args.setArgs(args)


# set download area area based primarly on posts,secondary on  prompt
def set_download_area(action=None):
    args = read_args.retriveArgs()
    action = action or args.action or {}
    if "download" not in action:
        return
    args.download_area = (
        areas.get_download_area()
        if len(areas.get_download_area()) > 0
        else prompts.download_areas_prompt()
    )
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
        prompts.scrape_paid_prompt() if args.scrape_paid != None else args.scrape_paid
    )
    write_args.setArgs(args)
