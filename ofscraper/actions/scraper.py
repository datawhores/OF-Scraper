r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import asyncio
import logging
import platform
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import ofscraper.api.archive as archive
import ofscraper.api.highlights as highlights
import ofscraper.api.labels as labels_api
import ofscraper.api.messages as messages
import ofscraper.api.paid as paid
import ofscraper.api.pinned as pinned
import ofscraper.api.profile as profile
import ofscraper.api.timeline as timeline
import ofscraper.classes.labels as labels
import ofscraper.classes.media as media
import ofscraper.classes.posts as posts_
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.db.operations as operations
import ofscraper.filters.media.main as filters
import ofscraper.utils.args.areas as areas
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.progress as progress_utils
import ofscraper.utils.system.free as free
import ofscraper.utils.system.system as system
from ofscraper.db.operations_.media import batch_mediainsert
from ofscraper.db.operations_.profile import (
    check_profile_table_exists,
    get_profile_info,
)
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")


@free.space_checker
async def process_messages(model_id, username, c):
    try:
        with stdout.lowstdout():
            messages_ = await messages.get_messages_progress(model_id, username, c=c)
            messages_ = list(
                map(lambda x: posts_.Post(x, model_id, username), messages_)
            )
            await operations.make_messages_table_changes(
                messages_,
                model_id=model_id,
                username=username,
            )

            log.debug(
                f"[bold]Messages media count with locked[/bold] {sum(map(lambda x:len(x.post_media),messages_))}"
            )
            log.debug("Removing locked messages media")
            output = []
            [output.extend(message.all_media) for message in messages_]
            log.debug(f"[bold]Messages media count[/bold] {len(output)}")
            # Update after database
            cache.set(
                f"{model_id}_scrape_messages",
                read_args.retriveArgs().after is not None
                and read_args.retriveArgs().after != 0,
            )

            return list(filter(lambda x: isinstance(x, media.Media), output)), messages_
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_paid_post(model_id, username, c):
    try:
        with stdout.lowstdout():
            paid_content = await paid.get_paid_posts_progress(username, model_id, c=c)
            paid_content = list(
                map(
                    lambda x: posts_.Post(x, model_id, username, responsetype="paid"),
                    paid_content,
                )
            )
            await operations.make_post_table_changes(
                paid_content,
                model_id=model_id,
                username=username,
            )
            output = []
            [output.extend(post.all_media) for post in paid_content]
            log.debug(f"[bold]Paid media count without locked[/bold] {len(output)}")

            await batch_mediainsert(
                output,
                model_id=model_id,
                username=username,
                downloaded=False,
            )

            return (
                list(filter(lambda x: isinstance(x, media.Media), output)),
                paid_content,
            )
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_stories(model_id, username, c):
    try:
        with stdout.lowstdout():
            stories = await highlights.get_stories_post_progress(model_id, c=c)
            stories = list(
                map(
                    lambda x: posts_.Post(
                        x, model_id, username, responsetype="stories"
                    ),
                    stories,
                )
            )
            await operations.make_stories_table_changes(
                stories,
                model_id=model_id,
                username=username,
            )

            log.debug(
                f"[bold]Story media count[/bold] {sum(map(lambda x:len(x.post_media), stories))}"
            )
            output = []
            [output.extend(stories.all_media) for stories in stories]
            await batch_mediainsert(
                output,
                model_id=model_id,
                username=username,
                downloaded=False,
            )

            return list(filter(lambda x: isinstance(x, media.Media), output)), stories
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_highlights(model_id, username, c):
    try:
        with stdout.lowstdout():
            highlights_ = await highlights.get_highlight_post_progress(model_id, c=c)
            highlights_ = list(
                map(
                    lambda x: posts_.Post(
                        x, model_id, username, responsetype="highlights"
                    ),
                    highlights_,
                )
            )
            await operations.make_stories_table_changes(
                highlights_,
                model_id=model_id,
                username=username,
            )

            log.debug(
                f"[bold]highlight media count[/bold] {sum(map(lambda x:len(x.post_media), highlights_))}"
            )
            output = []
            [output.extend(stories.all_media) for stories in highlights_]
            await batch_mediainsert(
                output,
                model_id=model_id,
                username=username,
                downloaded=False,
            )

            return (
                list(filter(lambda x: isinstance(x, media.Media), output)),
                highlights_,
            )
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_timeline_posts(model_id, username, c):
    try:
        with stdout.lowstdout():
            timeline_posts = await timeline.get_timeline_posts_progress(
                model_id, username, c=c
            )

            timeline_posts = list(
                map(
                    lambda x: posts_.Post(x, model_id, username, "timeline"),
                    timeline_posts,
                )
            )
            timeline_only_posts = list(
                filter(lambda x: x.regular_timeline, timeline_posts)
            )

            await operations.make_post_table_changes(
                timeline_only_posts,
                model_id=model_id,
                username=username,
            )
            log.debug(
                f"[bold]Timeline media count with locked[/bold] {sum(map(lambda x:len(x.post_media),timeline_only_posts))}"
            )
            log.debug("Removing locked timeline media")
            output = []
            [output.extend(post.all_media) for post in timeline_only_posts]
            log.debug(f"[bold]Timeline media count without locked[/bold] {len(output)}")

            await batch_mediainsert(
                output,
                model_id=model_id,
                username=username,
                downloaded=False,
            )
            cache.set(
                f"{model_id}_full_timeline_scrape",
                read_args.retriveArgs().after is not None,
            )
            return (
                list(filter(lambda x: isinstance(x, media.Media), output)),
                timeline_only_posts,
            )
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_archived_posts(model_id, username, c):
    try:
        with stdout.lowstdout():
            archived_posts = await archive.get_archived_posts_progress(
                model_id, username, c=c
            )
            archived_posts = list(
                map(
                    lambda x: posts_.Post(x, model_id, username, "archived"),
                    archived_posts,
                )
            )

            await operations.make_post_table_changes(
                archived_posts,
                model_id=model_id,
                username=username,
            )

            log.debug(
                f"[bold]Archived media count with locked[/bold] {sum(map(lambda x:len(x.post_media),archived_posts))}"
            )
            log.debug("Removing locked archived media")
            output = []
            [output.extend(post.all_media) for post in archived_posts]
            log.debug(f"[bold]Archived media count without locked[/bold] {len(output)}")

            await batch_mediainsert(
                output,
                model_id=model_id,
                username=username,
                downloaded=False,
            )
            cache.set(
                f"{model_id}_full_archived_scrape",
                read_args.retriveArgs().after is not None,
            )
            return (
                list(filter(lambda x: isinstance(x, media.Media), output)),
                archived_posts,
            )
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_pinned_posts(model_id, username, c):
    try:
        with stdout.lowstdout():
            pinned_posts = await pinned.get_pinned_posts_progress(model_id, c=c)
            pinned_posts = list(
                map(lambda x: posts_.Post(x, model_id, username), pinned_posts)
            )
            await operations.make_post_table_changes(
                pinned_posts,
                model_id=model_id,
                username=username,
            )

            log.debug(
                f"[bold]Pinned media count with locked[/bold] {sum(map(lambda x:len(x.post_media),pinned_posts))}"
            )
            log.debug("Removing locked pinned media")
            output = []
            [output.extend(post.all_media) for post in pinned_posts]
            log.debug(f"[bold]Pinned media count without locked[/bold] {len(output)}")

            await batch_mediainsert(
                output,
                model_id=model_id,
                username=username,
                downloaded=False,
            )

            return (
                list(filter(lambda x: isinstance(x, media.Media), output)),
                pinned_posts,
            )
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_profile(username) -> list:
    try:
        with stdout.lowstdout():
            user_profile = profile.scrape_profile(username)
            urls, info = profile.parse_profile(user_profile)
            profile.print_profile_info(info)
            output = []
            posts = []
            for count, data in enumerate(urls):
                post = posts_.Post(data, info[2], username, responsetype="profile")
                posts.append(post)
                output.append(
                    media.Media(
                        {
                            "url": data["url"],
                            "type": data["mediatype"],
                            "id": data["mediaid"],
                            "text": data["text"],
                        },
                        count,
                        post,
                    )
                )
            return output, posts
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
@run
async def process_all_paid():
    with stdout.lowstdout():
        paid_content = await paid.get_all_paid_posts()
        output = {}
        for model_id, value in paid_content.items():
            username = profile.scrape_profile(model_id).get("username")
            if username == constants.getattr(
                "DELETED_MODEL_PLACEHOLDER"
            ) and await check_profile_table_exists(
                model_id=model_id, username=username
            ):
                username = (
                    await get_profile_info(model_id=model_id, username=username)
                    or username
                )
            log.info(f"Processing {username}_{model_id}")
            await operations.table_init_create(model_id=model_id, username=username)
            log.debug(f"Created table for {username}_{model_id}")
            all_posts = list(
                map(
                    lambda x: posts_.Post(x, model_id, username, responsetype="paid"),
                    value,
                )
            )
            seen = set()
            new_posts = [
                post
                for post in all_posts
                if post.id not in seen and not seen.add(post.id)
            ]
            new_medias = [item for post in new_posts for item in post.all_media]
            new_medias = filters.filterMedia(new_medias)
            new_posts = filters.filterPost(new_posts)
            await operations.make_post_table_changes(
                new_posts,
                model_id=model_id,
                username=username,
            )
            await batch_mediainsert(
                new_medias,
                model_id=model_id,
                username=username,
                downloaded=False,
            )

            output[model_id] = dict(
                model_id=model_id, username=username, posts=new_posts, medias=new_medias
            )
            log.debug(
                f"[bold]Paid media count {username}_{model_id}[/bold] {len(new_medias)}"
            )

        log.debug(
            f"[bold]Paid Media for all models[/bold] {sum(map(lambda x:len(x['medias']),output.values()))}"
        )
        return output


@free.space_checker
async def process_labels(model_id, username, c):
    try:
        with stdout.lowstdout():
            labelled_posts_ = await labels_api.get_labels_progress(model_id, c=c)

            labelled_posts_labels = list(
                map(lambda x: labels.Label(x, model_id, username), labelled_posts_)
            )
            await operations.make_label_table_changes(
                labelled_posts_labels,
                model_id=model_id,
                username=username,
            )

            log.debug(
                f"[bold]Label media count with locked[/bold] {sum(map(lambda x:len(x),[post.post_media for labelled_post in labelled_posts_labels for post in labelled_post.posts]))}"
            )
            log.debug("Removing locked messages media")
            output = [
                post.all_media
                for labelled_post in labelled_posts_labels
                for post in labelled_post.posts
            ]
            log.debug(
                f"[bold]Label media count without locked[/bold] {sum(map(lambda x:len(x),output))}"
            )

            return [item for sublist in output for item in sublist], [
                post for ele in labelled_posts_labels for post in ele.posts
            ]
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@run
async def process_areas(ele, model_id) -> list:
    with stdout.lowstdout():
        executor = (
            ProcessPoolExecutor()
            if platform.system() not in constants.getattr("API_REQUEST_THREADONLY")
            else ThreadPoolExecutor()
        )
        try:
            with executor:
                asyncio.get_event_loop().set_default_executor(executor)
                username = ele.name
                output = []
                with progress_utils.setup_api_split_progress_live():
                    medias, posts = await process_task(model_id, username, ele)
                    output.extend(medias)
            return filters.filterMedia(output), filters.filterPost(posts)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())


async def process_task(model_id, username, ele):
    mediaObjs = []
    postObjs = []
    final_post_areas = set(areas.get_download_area())
    tasks = []
    async with sessionManager.sessionManager(
        sem=constants.getattr("API_REQ_SEM_MAX"),
        retries=constants.getattr("API_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
        total_timeout=constants.getattr("API_TIMEOUT_PER_TASK"),
        new_request_auth=True,
    ) as c:
        while True:
            max_count = min(
                constants.getattr("API_MAX_AREAS"),
                system.getcpu_count(),
                len(final_post_areas),
            )
            if not bool(tasks) and not bool(final_post_areas):
                break
            for _ in range(max_count - len(tasks)):
                if "Profile" in final_post_areas:
                    tasks.append(asyncio.create_task(process_profile(username)))
                    final_post_areas.remove("Profile")
                elif "Pinned" in final_post_areas:
                    tasks.append(
                        asyncio.create_task(process_pinned_posts(model_id, username, c))
                    )
                    progress_utils.pinned_layout.visible = True
                    final_post_areas.remove("Pinned")
                elif "Timeline" in final_post_areas:
                    tasks.append(
                        asyncio.create_task(
                            process_timeline_posts(model_id, username, c)
                        )
                    )
                    progress_utils.timeline_layout.visible = True
                    final_post_areas.remove("Timeline")
                elif "Archived" in final_post_areas:
                    tasks.append(
                        asyncio.create_task(
                            process_archived_posts(model_id, username, c)
                        )
                    )
                    progress_utils.archived_layout.visible = True
                    final_post_areas.remove("Archived")
                elif "Purchased" in final_post_areas:
                    tasks.append(
                        asyncio.create_task(process_paid_post(model_id, username, c))
                    )
                    progress_utils.paid_layout.visible = True
                    final_post_areas.remove("Purchased")
                elif "Messages" in final_post_areas:
                    tasks.append(
                        asyncio.create_task(process_messages(model_id, username, c))
                    )
                    final_post_areas.remove("Messages")
                    progress_utils.messages_layout.visible = True
                elif "Highlights" in final_post_areas:
                    tasks.append(
                        asyncio.create_task(process_highlights(model_id, username, c))
                    )
                    progress_utils.highlights_layout.visible = True
                    final_post_areas.remove("Highlights")
                elif "Stories" in final_post_areas:
                    tasks.append(
                        asyncio.create_task(process_stories(model_id, username, c))
                    )
                    progress_utils.stories_layout.visible = True
                    final_post_areas.remove("Stories")
                elif "Labels" in final_post_areas and ele.active:
                    tasks.append(
                        asyncio.create_task(process_labels(model_id, username, c))
                    )
                    progress_utils.labelled_layout.visible = True
                    final_post_areas.remove("Labels")
            if not bool(tasks):
                break
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            await asyncio.sleep(1)
            tasks = list(pending)
            for results in done:
                try:
                    medias, posts = await results
                    mediaObjs.extend(medias or [])
                    postObjs.extend(posts or [])
                    await asyncio.sleep(1)
                except Exception as E:
                    await asyncio.sleep(1)
                    log.debug(E)
                    continue
    return mediaObjs, postObjs
