import logging
import ofscraper.utils.logger as logger
import ofscraper.utils.args as args_
import ofscraper.commands.scraper as scraper
import ofscraper.commands.check as check
import ofscraper.commands.manual as manual
import ofscraper.utils.config as config_
import ofscraper.utils.profiles as profiles_




def main():
    log=logger.init_logger(logging.getLogger(__package__))
    args=args_.getargs()
    #print info
    log.debug(args)

    if vars(args).get("help"):
        quit()
    log.debug(f"config path: {str(config_.get_config_folder())}")
    log.debug(f"profile path: {str(profiles_.get_profile_path())}")

    


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
