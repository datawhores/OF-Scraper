import logging
import arrow
from rich.table import Table

import ofscraper.utils.console as console

import  ofscraper.runner.manager as manager
import ofscraper.utils.args.accessors.read as read_args
from ofscraper.db.operations_.media import (
    get_media_ids_downloaded_model,
    get_timeline_media,
    get_archived_media,
    get_messages_media,
)
from ofscraper.utils.logs.other import add_other_handler
from ofscraper.utils.context.run_async import run as run_async
import ofscraper.utils.actions as actions
import ofscraper.utils.constants as constants




def db():
    actions.select_areas()
    for model in manager.Manager.model_manager.getselected_usernames(rescan=False):
        print_media(model)

@run_async
async def get_all_media(username,model_id):
    args=read_args.retriveArgs()
    timeline=[]
    archived=[]
    messages=[]
    if "Timeline" in args.download_area:
        timeline = await get_timeline_media(model_id=model_id, username=username)
    if "Archived" in args.download_area:
         archived=get_archived_media(model_id=model_id, username=username)
    if "Messages" in args.download_area:
        messages=get_messages_media(model_id=model_id, username=username)
    return timeline+messages+archived
    # if len(curr) == 0:
    #     log.debug("Setting oldest date to zero because database is empty")
    #     return 0
    # curr_downloaded = await get_media_ids_downloaded_model(
    #     model_id=model_id, username=username
    # )

    # missing_items = list(
    #     filter(
    #         lambda x: x.get("downloaded") != 1
    #         and x.get("post_id") not in curr_downloaded
    #         and x.get("unlocked") != 0,
    #         curr,
    #     )
    # )

def print_dictionary_table(dictionaries, remove_keys=None):
    """Prints a list of dictionaries as a table.

    Args:
        dictionaries: A list of dictionaries to be printed.
        remove_keys: An optional list of keys to remove from the dictionaries before printing.
    """
    log = logging.getLogger("db")
    add_other_handler(log)


    # Remove specified keys from dictionaries (if provided)
    if remove_keys:
        remove_keys = remove_keys  if isinstance(remove_keys, list) else [remove_keys]
        for dictionary in dictionaries:
            for key in remove_keys:
                dictionary.pop(key, None)

    #modify dictionary
    for dictionary in dictionaries:
        dictionary["posted_at"]=arrow.get(dictionary["posted_at"]).format(constants.getattr("API_DATE_FORMAT"))
        dictionary["created_at"]=arrow.get(dictionary["created_at"]).format(constants.getattr("API_DATE_FORMAT"))
    # Get the unique keys from all dictionaries
    keys = set()
    for dictionary in dictionaries:
        keys.update(dictionary.keys())

    table=Table(title="Database Table")

    #  log the header row with column names
    header_row = "|".join(f"{key:^20}" for key in keys)
    value=f"|{'=' * 20}|{header_row}|{'-' * 20}|"
    log.warning(value)
    #add to table
    for key in keys:
        table.add_column(key, justify="center")
 

    for dictionary in dictionaries:
         # Print the data rows
        row_data = [str(dictionary.get(key, "")) for key in keys]
        row = "|".join(f"{str(value):^20}" for value in row_data)
        log.warning(f"|{' ' * 20}|{row}|{'-' * 20}|")
        # add to table
        table.add_row(*row_data)
    console.get_console().print(table)

def print_media(model):
    model_id = model.id
    username=model.name
    media=get_all_media(username,model_id)
    print_dictionary_table(media,remove_keys=["link","linked"])