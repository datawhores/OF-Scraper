"""
                                                             
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
import copy
from ofscraper.utils.context.run_async import run
import ofscraper.utils.args.accessors.read as read_args
from ofscraper.commands.helpers.strings import metadata_activity_str,all_paid_metadata_str,all_paid_progress_metadata_str
from ofscraper.commands.helpers.scrape_paid import process_scrape_paid,process_user_info_printer,process_user
import ofscraper.utils.args.mutators.write as write_args

log = logging.getLogger("shared")
@run
async def metadata_paid_all():
    old_args = copy.deepcopy(read_args.retriveArgs())
    force_change_metadata()
    out=["[bold yellow]Scrape Paid Results[/bold yellow]"]

    async for count,value,length in process_scrape_paid():
        process_user_info_printer(value,length,count,all_paid_update=all_paid_metadata_str,all_paid_activity=metadata_activity_str,
        log_progress=all_paid_progress_metadata_str

                                  
                                  )
        out.append(await process_user(value,length))
    write_args.setArgs(old_args)
    return out

def force_change_metadata():
    args = read_args.retriveArgs()
    args.metadata = args.scrape_paid
    write_args.setArgs(args)