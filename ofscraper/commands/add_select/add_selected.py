import ofscraper.utils.actions as actions
import ofscraper.utils.args.read as read_args
from ofscraper.commands.actions.download.download import process_post, scrape_paid_all
from ofscraper.commands.actions.like import process_like, process_unlike


def add_selected_areas():
    functs = []
    action = read_args.retriveArgs().action
    if "like" in action and "download" in action:
        actions.select_areas()
        functs.append(process_post)
        functs.append(process_like)
    elif "unlike" in action and "download" in action:
        actions.select_areas()
        functs.append(process_post)
        functs.append(process_unlike)
    elif "download" in action:
        actions.select_areas()
        functs.append(process_post)
    elif "like" in action:
        actions.select_areas()
        functs.append(process_like)
    elif "unlike" in action:
        actions.select_areas()
        functs.append(process_unlike)
    if read_args.retriveArgs().scrape_paid:
        functs.append(scrape_paid_all)
    return functs
