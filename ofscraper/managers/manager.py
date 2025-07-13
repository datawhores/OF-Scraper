import time
from contextlib import contextmanager, asynccontextmanager

import ofscraper.main.close.exit as exit_manager
import ofscraper.utils.console as console
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.system.system as system
from ofscraper.managers.model import ModelManager
from ofscraper.managers.stats import StatsManager
from ofscraper.commands.db import db
import ofscraper.commands.metadata.metadata as metadata
import ofscraper.commands.scraper.scraper as actions
import ofscraper.commands.manual as manual
import ofscraper.commands.check as check
import ofscraper.utils.settings as settings
import ofscraper.managers.sessionmanager.ofsession as OFsessionManager
import ofscraper.managers.sessionmanager.sessionmanager as sessionManager


Manager = None


def start_manager():
    global Manager
    if not isinstance(Manager, mainManager):
        Manager = mainManager()
        Manager.start_managers()
        Manager.start()


def start_other_managers():
    global Manager
    if not isinstance(Manager, mainManager):
        Manager = mainManager()
        Manager.start_managers()


class mainManager:
    def __init__(self) -> None:
        self.model_manager = None
        self.stats_manager = None

    def start(self):
        self.initLogs()
        time.sleep(3)
        self.print_name()
        self.pick()
        exit_manager.shutdown()

    def start_managers(self):
        if self.model_manager is None:
            self.model_manager = ModelManager()
        if self.stats_manager is None:
            self.stats_manager = StatsManager()

    def pick(self):
        if settings.get_settings().command in [
            "post_check",
            "msg_check",
            "paid_check",
            "story_check",
        ]:
            check.checker()
        elif settings.get_settings().command == "metadata":
            metadata.process_selected_areas()
        elif settings.get_settings().command == "manual":
            manual.manual_download()
        elif settings.get_settings().command == "db":
            db()
        else:
            actions.main()

    def print_name(self):
        console.get_shared_console().print(
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
        )

    def initLogs(self):
        if len(system.get_dupe_ofscraper()) > 0:
            console.get_shared_console().print(
                "[bold yellow]Warning another OF-Scraper instance was detected[bold yellow]\n\n\n"
            )
        logs.printStartValues()

    @contextmanager
    def get_session(self, *args, **kwargs):

        with sessionManager.sessionManager(*args, **kwargs) as c:
            yield c

    @contextmanager
    def get_ofsession(self, *args, **kwargs):

        with OFsessionManager.OFSessionManager(*args, **kwargs) as c:
            yield c

    @asynccontextmanager
    async def aget_ofsession(self, *args, **kwargs):

        async with OFsessionManager.OFSessionManager(*args, **kwargs) as c:
            yield c

    @contextmanager
    def get_subscription_session(self, *args, **kwargs):
        with OFsessionManager.SubscriptionSessionManager(*args, **kwargs) as c:
            yield c

    @asynccontextmanager
    async def aget_subscription_session(self, *args, **kwargs):
        async with OFsessionManager.SubscriptionSessionManager(*args, **kwargs) as c:
            yield c

    @asynccontextmanager
    async def get_download_session(self, *args, **kwargs):

        async with OFsessionManager.download_session(*args, **kwargs) as c:
            yield c

    @asynccontextmanager
    async def get_metadata_session(self, *args, **kwargs):
        async with OFsessionManager.metadata_session(*args, **kwargs) as c:
            yield c

    @asynccontextmanager
    async def get_cdm_session_manual(self, *args, **kwargs):

        async with OFsessionManager.cdm_session_manual(*args, **kwargs) as c:
            yield c

    @asynccontextmanager
    async def get_cdm_session(self, *args, **kwargs):

        async with OFsessionManager.cdm_session(*args, **kwargs) as c:
            yield c

    @contextmanager
    def get_like_session(self, *args, **kwargs):
        with OFsessionManager.like_session(*args, **kwargs) as c:
            yield c
