def main():
    try:
        import logging
        import sys
        import time
        import traceback

        from diskcache import Cache

        import ofscraper.commands.picker as picker
        import ofscraper.utils.args.parse as args_parse
        import ofscraper.utils.config.config as config_
        import ofscraper.utils.config.data as data
        import ofscraper.utils.console as console
        import ofscraper.utils.context.exit as exit
        import ofscraper.utils.logger as logger
        import ofscraper.utils.manager as manager
        import ofscraper.utils.paths.manage as paths_manage
        import ofscraper.utils.paths.paths as paths
        import ofscraper.utils.startvals as startvals
        import ofscraper.utils.system.system as system

        system.setName()
        system.set_mulitproc_start_type()
        config_.read_config()
        if len(system.get_dupe_ofscraper()) > 0:
            console.get_shared_console().print(
                "[bold yellow]Warning another OF-Scraper instance was detected[bold yellow]\n\n\n"
            )

        logger.init_values()
        system.set_eventloop()
        logger.get_shared_logger()
        startvals.printStartValues()
        logger.discord_warning()
        args = args_parse.parse_args()
        if vars(args).get("help"):
            return
        logger.start_stdout_logthread()
        logger.start_other_helper()
        # allow background processes to start
        time.sleep(3)

        paths_manage.make_folders()
        picker.pick()
        logger.gracefulClose()
        manager.shutdown()
    except SystemExit:
        print(f"Arguments {sys.argv}")
    except KeyboardInterrupt as E:
        console.get_shared_console().print("handling force closing of script")
        try:
            with exit.DelayedKeyboardInterrupt():
                logger.forcedClose()
                manager.shutdown()
                try:
                    cache = Cache(
                        paths.getcachepath(),
                        disk=data.get_cache_mode(),
                    )
                    cache.close()
                    raise E
                except Exception as E:
                    with exit.DelayedKeyboardInterrupt():
                        raise E

        except KeyboardInterrupt as E:
            with exit.DelayedKeyboardInterrupt():
                logger.forcedClose()
                manager.shutdown()
                raise E
    except Exception as E:
        logging.getLogger("shared").traceback_(traceback.format_exc())
        logging.getLogger("shared").traceback_(E)
        try:
            with exit.DelayedKeyboardInterrupt():
                logger.forcedClose()
                manager.shutdown()
                try:
                    cache = Cache(
                        paths.getcachepath(),
                        disk=data.get_cache_mode(),
                    )
                    cache.close()

                    raise E
                except Exception as E:
                    with exit.DelayedKeyboardInterrupt():
                        raise E

        except KeyboardInterrupt as E:
            with exit.DelayedKeyboardInterrupt():
                logger.forcedClose()
                if logger.queue_:
                    logger.queue_.close()
                    logger.queue_.cancel_join_thread()
                manager.shutdown()
                raise
