import logging
import ofscraper.utils.logger as logger
import ofscraper.utils.args as args_
import ofscraper.commands.scraper as scraper
import ofscraper.commands.check as check
import ofscraper.commands.manual as manual
import ofscraper.utils.config as config_
import ofscraper.utils.profiles as profiles_
import ofscraper.utils.paths as paths_
import ssl
import platform
import certifi


def main():
    startvalues()
    args=args_.getargs()
    if vars(args).get("help"):
        quit()
  

    make_folders()
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
    else:
        scraper.main()

def make_folders():
    config_.get_config_folder()
    profiles_.create_profile_path()

def startvalues():
    args=args_.getargs()
    log=logger.init_logger(logging.getLogger(__package__))
    logger.updateSenstiveDict(paths_.get_username(),"your_username")
    #print info
    log.debug(args)
    log.debug(config_.read_config())
    log.info(f"config path: {str(paths_.get_config_path())}")
    log.info(f"profile path: {str(paths_.get_profile_path())}")
    log.info(f"log folder: {str(paths_.get_config_home()/'logging')}")
    log.debug(f"ssl {ssl.get_default_verify_paths()}")
    log.debug(f"python version {platform. python_version()}" )
    log.debug(f"certifi {certifi.where()}")
    