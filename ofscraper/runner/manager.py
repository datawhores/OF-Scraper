import time
from contextlib import contextmanager,asynccontextmanager

import ofscraper.runner.close.exit as exit_manager
import ofscraper.utils.console as console
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.system.system as system
from ofscraper.data.models.manager import ModelManager
from ofscraper.commands.runners.db import db

Manager=None
def start_manager():
    global Manager
    if not isinstance(Manager,mainManager):
        Manager=mainManager()
        Manager.start_managers()
        Manager.start()
def start_other_managers():
    global Manager
    if not isinstance(Manager,mainManager):
        Manager=mainManager()
        Manager.start_managers()

class mainManager():
    def __init__(self) -> None:
        self.model_manager = None
    
    
    
        

    def start(self):
        self.initLogs()
        time.sleep(3)
        self.print_name()
        self.pick()
        exit_manager.shutdown()
    
    def start_managers(self):
        if self.model_manager is None:
            self.model_manager = ModelManager()
    
    def pick(self):
        import ofscraper.commands.runners.check as check
        import ofscraper.commands.runners.manual as manual
        import ofscraper.commands.runners.metadata.metadata as metadata
        import ofscraper.commands.runners.scraper.scraper as actions
        from ofscraper.utils.args.accessors.command import get_command
        if get_command()  in ["post_check", "msg_check", "paid_check", "story_check"]:
            check.checker()
        elif get_command() == "metadata":
            metadata.process_selected_areas()
        elif get_command()  == "manual":
            manual.manual_download()
        elif get_command()  == "db":
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
    @ contextmanager
    def get_session(self,*args,**kwargs):
        import ofscraper.classes.sessionmanager.sessionmanager as sessionManager
        with sessionManager.sessionManager(*args, **kwargs) as c:
            yield c

    @ contextmanager
    def get_ofsession(self,*args,**kwargs):
        import ofscraper.classes.sessionmanager.ofsession as OFsessionManager
        with OFsessionManager.OFSessionManager(*args, **kwargs) as c:
            yield c    


    @ asynccontextmanager
    async def aget_ofsession(self,*args,**kwargs):
        import ofscraper.classes.sessionmanager.ofsession as OFsessionManager
        async with OFsessionManager.OFSessionManager(*args, **kwargs) as c:
            yield c  