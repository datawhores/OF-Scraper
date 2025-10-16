import time
from typing import Union

import ofscraper.main.close.exit as exit_manager
import ofscraper.utils.console as console
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.system.system as system
from ofscraper.managers.model import ModelManager


from ofscraper.commands.db import db
import ofscraper.commands.metadata.metadata as metadata
import ofscraper.commands.scraper.scraper as actions
import ofscraper.commands.manual as manual
import ofscraper.commands.check as check
import ofscraper.utils.settings as settings


# Forward declarations for type hinting to prevent circular imports
class StatsManager: 
    pass
class ProfileManager: 
    pass
class SessionHandler: 
    pass

Manager = None

def start_manager():
    global Manager
    if not isinstance(Manager, mainManager):
        Manager = mainManager()
        Manager.start()


class mainManager:
    def __init__(self) -> None:
        self._stats_manager:Union[None, StatsManager] = None
        self._profile_manager:Union[None, ProfileManager]=None
        self._session:Union[None, SessionHandler]=None

    def start(self):
        self.initLogs()
        time.sleep(3)
        self.print_name()
        self.pick()
        exit_manager.shutdown()


    @property
    def profile_manager(self) -> ProfileManager:
        """
        Lazily initializes and returns the ProfileManager instance.
        """
        if self._profile_manager is None:
            from ofscraper.managers.profile import ProfileManager
            self._profile_manager = ProfileManager()
        return self._profile_manager

    @property
    def session(self) -> SessionHandler:
        """
        Lazily initializes and returns the SessionHandler instance.
        """
        if self._session is None:
            from ofscraper.managers.sessionHandler import SessionHandler
            self._session = SessionHandler()
        return self._session

    @property
    def stats_manager(self) -> StatsManager:
        """
        Lazily initializes and returns the StatsManager instance.
        This prevents circular imports at startup.
        """
        if self._stats_manager is None:
            # Import is moved inside the property, delaying it until first access
            from ofscraper.managers.stats import StatsManager
            self._stats_manager = StatsManager()
        return self._stats_manager

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

    @property
    def current_model_manager(self) -> ModelManager:
        """
        Gets the ModelManager for the currently active profile.
        If a manager for this profile doesn't exist, it creates one.
        """
        return self.profile_manager.current_model_manager
