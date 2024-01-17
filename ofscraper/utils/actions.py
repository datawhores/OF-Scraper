r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args as args_
import ofscraper.utils.system as system


def reset_download():
    args = args_.getargs()

    if bool(args.download_area) and prompts.reset_download_areas_prompt() == "Yes":
        args.scrape_paid = None
        args.download_area = {}


def reset_like():
    args = args_.getargs()
    if bool(args.like_area) and prompts.reset_like_areas_prompt() == "Yes":
        args.like_area = {}


@system.space_checker
def select_areas(action=None, reset=False):
    args = args_.getargs()
    action = action or args.action
    if "download" in action and reset:
        reset_download()
    elif ("like" or "unlike") in action and reset:
        reset_like()
    args_.changeargs(args)
    set_post_area(action)
    set_download_area(action)
    set_scrape_paid(action)
    set_like_area(action)
    remove_post_area()


def remove_post_area():
    args = args_.getargs()
    args.posts = {}
    args_.changeargs(args)


@system.space_checker
# set post for primarily for download-area, secondary for like/unlike
def set_post_area(action=None):
    args = args_.getargs()
    action = action or args.action or {}
    if "download" not in action:
        return
    elif len(args_.get_download_area()) > 0:
        return
    elif len(args.posts) > 0:
        return
    args.posts = prompts.areas_prompt()
    args_.changeargs(args)


# set download_area based on posts
def set_download_area(action=None):
    args = args_.getargs()
    action = action or args.action or {}
    if "download" not in action:
        return
    args.download_area = args_.get_download_area()


def set_scrape_paid(action=None):
    args = args_.getargs()
    action = action or args.action or {}
    if "download" not in action:
        return
    args.scrape_paid = (
        prompts.scrape_paid_prompt() if args.scrape_paid != None else args.scrape_paid
    )
    args_.changeargs(args)


# set like area based primarly on posts,secondary on from prompt
def set_like_area(action=None):
    args = args_.getargs()
    action = action or args.action or {}
    if "like" not in action and "unlike" not in action:
        return
    args.like_area = (
        args_.get_like_area()
        if len(args_.get_like_area()) > 0
        else prompts.like_areas_prompt()
    )
    args_.changeargs(args)
