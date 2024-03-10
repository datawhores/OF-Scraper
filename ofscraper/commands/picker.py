import ofscraper.commands.check as check
import ofscraper.commands.manual as manual
import ofscraper.commands.scraper as scraper
import ofscraper.utils.args.read as read_args


def pick():
    args = read_args.retriveArgs()
    if args.command in ["post_check", "msg_check", "paid_check", "story_check"]:
        check.checker()
    elif args.command == "manual":
        manual.manual_download()
    else:
        scraper.main()
