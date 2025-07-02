import logging
import traceback
import threading
import schedule
import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.screens as progress_utils
from ofscraper.commands.utils.scrape_context import scrape_context_manager
from ofscraper.utils.checkers import check_auth
from ofscraper.main.close.final.final import final_action
from ofscraper.data.posts.scrape_paid import scrape_paid_all
from ofscraper.commands.scraper.actions.download.download import downloader
import ofscraper.commands.scraper.actions.like.like as like_action
import ofscraper.utils.live.updater as progress_updater
import ofscraper.db.operations as operations
from ofscraper.utils.context.run_async import run as run_async
from ofscraper.data.posts.post import post_media_process
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.paths.paths as paths
import ofscraper.utils.system.network as network
from ofscraper.commands.scraper.utils.prepare import prepare
import ofscraper.utils.console as console
from ofscraper.commands.utils.command import commmandManager
import ofscraper.utils.actions as actions
import ofscraper.utils.checkers as checkers
import ofscraper.main.manager as manager
from ofscraper.commands.scraper.utils.schedule import set_schedule
import ofscraper.utils.config.data as data
import ofscraper.utils.menu as menu
from ofscraper.commands.scraper.utils.jobqueue import jobqueue
from ofscraper.__version__ import __version__
import ofscraper.utils.settings as settings
from ofscraper.utils.logs.logger import flushlogs


log = logging.getLogger("shared")


class scraperManager(commmandManager):
    def __init__(self):
        super().__init__()

    @exit.exit_wrapper
    def runner(self, menu=False):
        check_auth()
        with scrape_context_manager():
            normal_data = []
            user_first_data = []
            scrape_paid_data = []
            userdata = []

            with progress_utils.setup_activity_group_live(
                setup=True, revert=False, stop=True
            ):
                if settings.get_settings().scrape_paid:
                    scrape_paid_data = scrape_paid_all()

                if not self.run_action:
                    pass

                elif settings.get_settings().users_first:
                    userdata, session = prepare(menu=menu)
                    user_first_data = self._process_users_actions_user_first(
                        userdata, session
                    )
                else:
                    userdata, session = prepare()
                    normal_data = self._process_users_actions_normal(userdata, session)
            final_action(normal_data, scrape_paid_data, user_first_data)

    @exit.exit_wrapper
    @run_async
    async def _process_users_actions_user_first(self, userdata, session):
        data = await self._get_userfirst_data_function(self._get_users_data_user_first)(
            userdata, session
        )
        progress_updater.update_activity_task(description="Performing Actions on Users")
        progress_updater.update_user_activity(
            description="Users with Actions completed", completed=0
        )
        flushlogs()
        return await self._get_userfirst_action_execution_function(
            self._execute_user_action
        )(data)

    async def _get_users_data_user_first(self, session, ele):
        return await self._process_ele_user_first_data_retriver(ele, session)

    async def _process_ele_user_first_data_retriver(self, ele, session):
        model_id = ele.id
        username = ele.name
        avatar = ele.avatar
        await operations.table_init_create(model_id=model_id, username=username)
        postcollection = await post_media_process(ele, session)
        return {
            model_id: {
                "username": username,
                "posts": postcollection.get_posts_for_text_download(),
                "media": postcollection.get_media_to_download(),
                "avatar": avatar,
                "like_posts": postcollection.get_posts_to_like(),
                "ele": ele,
            }
        }

    async def _execute_user_action(
        self, posts=None, like_posts=None, ele=None, media=None
    ):
        actions = settings.get_settings().action
        username = ele.name
        model_id = ele.id
        out = []
        for action in actions:
            if action == "download":
                result, _ = await downloader(
                    posts=posts,
                    media=media,
                    model_id=model_id,
                    username=username,
                )
                out.append(result)
            elif action == "like":
                out.append(
                    like_action.process_like(
                        ele=ele,
                        posts=like_posts,
                        media=media,
                        model_id=model_id,
                        username=username,
                    )
                )
            elif action == "unlike":
                out.append(
                    like_action.process_unlike(
                        ele=ele,
                        posts=like_posts,
                        media=media,
                        model_id=model_id,
                        username=username,
                    )
                )
            manager.Manager.model_manager.mark_as_processed(username)
        return out

    @exit.exit_wrapper
    @run_async
    async def _process_users_actions_normal(self, userdata=None, session=None):
        progress_updater.update_user_activity(
            description="Users with Actions Completed"
        )
        flushlogs()
        return await self._get_user_action_function(self._execute_user_action)(
            userdata, session
        )


def main():
    try:
        print_start()
        paths.temp_cleanup()
        paths.cleanDB()
        network.check_cdm()

        scrapper()
        paths.temp_cleanup()
        paths.cleanDB()
    except KeyboardInterrupt:
        try:
            with exit.DelayedKeyboardInterrupt():
                paths.temp_cleanup()
                paths.cleanDB()
                raise KeyboardInterrupt
        except KeyboardInterrupt:
            raise KeyboardInterrupt
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                paths.temp_cleanup()
                paths.cleanDB()
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                raise E


def daemon_process():
    checkers.check_auth()
    worker_thread = None
    scrapingManager = scraperManager()

    jobqueue.put(scrapingManager.runner)
    if settings.get_settings().output_level == "PROMPT":
        log.info("[bold]silent-mode on[/bold]")
    log.info("[bold]Daemon mode on[/bold]")
    manager.Manager.model_manager.get_selected_models()
    actions.select_areas()
    try:
        worker_thread = threading.Thread(
            target=set_schedule, args=[scrapingManager.runner], daemon=True
        )
        worker_thread.start()
        # Check if jobqueue has function
        while True:
            try:
                job_func = jobqueue.get()
                job_func()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
            finally:
                jobqueue.task_done()
    except KeyboardInterrupt as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
            raise KeyboardInterrupt
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
                raise E
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
            raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
                raise E


@exit.exit_wrapper
def process_prompts():
    while True:
        if menu.main_menu_action():
            break
        elif prompts.continue_prompt() == "No":
            break


def process_selected_areas():
    log.debug("[bold deep_sky_blue2] Running Action Mode [/bold deep_sky_blue2]")
    scrapingManager = scraperManager()
    scrapingManager.runner()
    while True:
        if not data.get_InfiniteLoop() or prompts.continue_prompt() == "No":
            break
        action = prompts.action_prompt()
        if action == "main":
            process_prompts()
            break
        elif action == "quit":
            break
        else:
            menu.get_count() > 0 and menu.reset_menu_helper()
            scrapingManager.runner()
            menu.update_count()


def scrapper():
    global selectedusers
    selectedusers = None
    args = settings.get_args()
    if args.daemon:
        if len(args.action) == 0 and not args.scrape_paid:
            prompts.action_prompt()
        daemon_process()
    elif len(args.action) > 0 or args.scrape_paid:
        process_selected_areas()
    elif len(args.action) == 0:
        process_prompts()


def print_start():
    console.get_shared_console().print(
        f"[bold green]Version {__version__}[/bold green]"
    )
