import ofscraper.commands.runners.check as check
import ofscraper.commands.runners.manual as manual
import ofscraper.commands.runners.metadata.metadata as metadata
import ofscraper.commands.runners.scraper.scraper as actions
import ofscraper.utils.args.accessors.read as read_args


def pick():
    args = read_args.retriveArgs()
    if args.command in ["post_check", "msg_check", "paid_check", "story_check"]:
        check.checker()
    elif args.command == "metadata":
        metadata.process_selected_areas()
    elif args.command == "manual":
        manual.manual_download()
    else:
        actions.main()