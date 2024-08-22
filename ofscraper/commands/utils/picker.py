import ofscraper.commands.runners.check as check
import ofscraper.commands.runners.manual as manual
import ofscraper.commands.runners.metadata.metadata as metadata
import ofscraper.commands.runners.scraper.scraper as actions
from ofscraper.utils.args.accessors.command import get_command



def pick():
    if get_command()  in ["post_check", "msg_check", "paid_check", "story_check"]:
        check.checker()
    elif get_command() == "metadata":
        metadata.process_selected_areas()
    elif get_command()  == "manual":
        manual.manual_download()
    else:
        actions.main()
