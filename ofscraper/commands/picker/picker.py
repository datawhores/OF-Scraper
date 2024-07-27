import ofscraper.commands.commands.check as check
import ofscraper.commands.commands.manual as manual
import ofscraper.commands.commands.metadata.metadata as metadata
import ofscraper.commands.commands.scraper.manager.manager as actions
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
