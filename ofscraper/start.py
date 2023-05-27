import logging
import ofscraper.utils.logger as logger
import ofscraper.utils.args as args_
import ofscraper.commands.scraper as scraper
import ofscraper.commands.check as check
log=logger.init_logger(logging.getLogger(__package__))
args=args_.getargs()
log.debug(args)
def main():
    if args.command=="check":
        check.main()
    elif args.command=="manual":
        None
    else:
        scraper.main()
