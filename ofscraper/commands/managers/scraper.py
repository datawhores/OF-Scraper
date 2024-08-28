from ofscraper.commands.managers.manager import commmandManager
import logging
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.screens as progress_utils
from ofscraper.commands.utils.scrape_context import scrape_context_manager
from ofscraper.commands.runners.scraper.utils.prepare import prepare
from ofscraper.utils.checkers import check_auth
from ofscraper.runner.close.final.final import final
from ofscraper.data.posts.scrape_paid import scrape_paid_all
from ofscraper.actions.actions.download.download import downloader
import ofscraper.actions.actions.like.like as like_action
import ofscraper.utils.live.updater as progress_updater
import ofscraper.db.operations as operations
from ofscraper.utils.context.run_async import run as run_async
from ofscraper.data.posts.post import post_media_process


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
                if read_args.retriveArgs().scrape_paid:
                    scrape_paid_data = scrape_paid_all()

                if not self.run_action:
                    pass

                elif read_args.retriveArgs().users_first:
                    userdata, session = prepare(menu=menu)
                    user_first_data = self._process_users_actions_user_first(
                        userdata, session
                    )
                else:
                    userdata, session = prepare()
                    normal_data = self._process_users_actions_normal(userdata, session)
            final(normal_data, scrape_paid_data, user_first_data)

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
        media, posts, like_posts = await post_media_process(ele, session)
        return {
            model_id: {
                "username": username,
                "posts": posts,
                "media": media,
                "avatar": avatar,
                "like_posts": like_posts,
                "ele": ele,
            }
        }

    async def _execute_user_action(
        self, posts=None, like_posts=None, ele=None, media=None
    ):
        actions = read_args.retriveArgs().action
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
        return out

    @exit.exit_wrapper
    @run_async
    async def _process_users_actions_normal(self, userdata=None, session=None):
        progress_updater.update_user_activity(
            description="Users with Actions Completed"
        )
        return await self._get_user_action_function(self._execute_user_action)(
            userdata, session
        )
