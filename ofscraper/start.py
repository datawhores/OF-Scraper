import logging
import ofscraper.utils.logger as logger
import ofscraper.utils.args as args_
import ofscraper.commands.scraper as scraper
import ofscraper.commands.check as check
import ofscraper.commands.manual as manual


log=logger.init_logger(logging.getLogger(__package__))
args=args_.getargs()
log.debug(args)
def main():
    import ofscraper.utils.binaries as binaries
    binaries.ffmpeg_mac()
    binaries.mp4_decrypt_mac()

    return
    if args.command=="post_check":
        check.post_checker()
    elif args.command=="msg_check":
        check.message_checker()
    elif args.command=="paid_check":
        check.purchase_checker()
    elif args.command=="story_check":
        check.stories_checker()
    elif args.command=="manual":
        manual.manual_download()
    elif vars(args).get("help"):
        None
    else:
        scraper.main()
