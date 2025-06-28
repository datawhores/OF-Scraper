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
import traceback
from functools import partial

import ofscraper.data.api.archive as archive
import ofscraper.data.api.highlights as highlights
import ofscraper.data.api.labels as labels_api
import ofscraper.data.api.messages as messages
import ofscraper.data.api.paid as paid
import ofscraper.data.api.pinned as pinned
import ofscraper.data.api.profile as profile
import ofscraper.data.api.streams as streams
import ofscraper.data.api.timeline as timeline
import ofscraper.classes.labels as labels
import ofscraper.classes.of.posts as posts_
import ofscraper.db.operations as operations
import ofscraper.filters.media.main as filters
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
import ofscraper.utils.system.free as free
from ofscraper.data.api.common.cache.write import set_after_checks
from ofscraper.commands.utils.strings import all_paid_model_id_str, all_paid_str
from ofscraper.db.operations_.media import batch_mediainsert
from ofscraper.db.operations_.profile import (
    check_profile_table_exists,
    get_profile_info,
)
from ofscraper.utils.args.accessors.areas import (
    get_download_area,
    get_final_posts_area,
    get_like_area,
    get_text_area,
)
from ofscraper.utils.context.run_async import run
import ofscraper.utils.settings as settings
from ofscraper.classes.of.postcollection import PostCollection

log = logging.getLogger("shared")


@run
async def post_media_process(ele, c=None) -> PostCollection:

    username = ele.name
    model_id = ele.id
    await operations.table_init_create(model_id=model_id, username=username)
    postcollection = await process_areas(ele, model_id, username, c=c)
    return postcollection


@free.space_checker
async def process_messages(model_id, username, c):
    try:
        messages_ = await messages.get_messages(
            model_id, username, c=c, post_id=settings.get_settings().post_id
        )
        messages_ = list(map(lambda x: posts_.Post(x, model_id, username), messages_))
        await operations.make_messages_table_changes(
            messages_,
            model_id=model_id,
            username=username,
        )
        set_after_checks(model_id, messages.API)

        return messages_, messages.API
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_paid_post(model_id, username, c):
    try:
        paid_content = await paid.get_paid_posts(username, model_id, c=c)
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
        return (paid_content, paid.API)
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_stories(model_id, username, c):
    try:
        stories = await highlights.get_stories_post(model_id, c=c)
        stories = list(
            map(
                lambda x: posts_.Post(
                    x, model_id, username, responsetype=highlights.API_S
                ),
                stories,
            )
        )
        await operations.make_stories_table_changes(
            stories,
            model_id=model_id,
            username=username,
        )

        return stories, highlights.API_S
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_highlights(model_id, username, c):
    try:
        highlights_ = await highlights.get_highlight_post(model_id, c=c)
        highlights_ = list(
            map(
                lambda x: posts_.Post(
                    x, model_id, username, responsetype=highlights.API_H
                ),
                highlights_,
            )
        )
        await operations.make_stories_table_changes(
            highlights_,
            model_id=model_id,
            username=username,
        )

        return (highlights_, highlights.API_H)
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_timeline_posts(model_id, username, c):
    try:
        timeline_posts = await timeline.get_timeline_posts(
            model_id, username, c=c, post_id=settings.get_settings().post_id
        )

        timeline_posts = list(
            map(
                lambda x: posts_.Post(x, model_id, username, timeline.API),
                timeline_posts,
            )
        )
        timeline_only_posts = timeline.filter_timeline_post(timeline_posts)

        await operations.make_post_table_changes(
            timeline_only_posts,
            model_id=model_id,
            username=username,
        )
        set_after_checks(model_id, timeline.API)
        return (timeline_only_posts, timeline.API)
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_archived_posts(model_id, username, c):
    try:
        archived_posts = await archive.get_archived_posts(
            model_id, username, c=c, post_id=settings.get_settings().post_id
        )
        archived_posts = list(
            map(
                lambda x: posts_.Post(x, model_id, username, archive.API),
                archived_posts,
            )
        )

        await operations.make_post_table_changes(
            archived_posts,
            model_id=model_id,
            username=username,
        )

        set_after_checks(model_id, archive.API)
        return (archived_posts, archive.API)
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_streamed_posts(model_id, username, c):
    try:
        streams_posts = await streams.get_streams_posts(
            model_id, username, c=c, post_id=settings.get_settings().post_id
        )
        streams_posts = list(
            map(
                lambda x: posts_.Post(x, model_id, username, streams.API),
                streams_posts,
            )
        )

        await operations.make_post_table_changes(
            streams_posts,
            model_id=model_id,
            username=username,
        )

        set_after_checks(model_id, streams.API)
        return (streams_posts, streams.API)
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_pinned_posts(model_id, username, c):
    try:
        pinned_posts = await pinned.get_pinned_posts(
            model_id, c=c, post_id=settings.get_settings().post_id
        )
        pinned_posts = list(
            map(lambda x: posts_.Post(x, model_id, username), pinned_posts)
        )
        await operations.make_post_table_changes(
            pinned_posts,
            model_id=model_id,
            username=username,
        )

        return (pinned_posts, pinned.API)
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_profile(username) -> list:
    try:
        user_profile = profile.scrape_profile(username)
        urls, info = profile.parse_profile(user_profile)
        profile.print_profile_info(info)
        posts = []
        for count, data in enumerate(urls):
            post = posts_.Post(data, info[2], username, responsetype=profile.API)
            posts.append(post)
        return posts, profile.API
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
@run
async def process_all_paid():
    with progress_utils.setup_api_split_progress_live():
        paid_content = await paid.get_all_paid_posts()
    output = {}
    with progress_utils.setup_all_paid_database_live():
        progress_updater.update_activity_task(
            description="Processsing Paid content data"
        )
        actions = ["download"]
        if get_text_area():
            actions.append("text")
        for model_id, value in paid_content.items():
            progress_updater.update_activity_count(
                total=None, description=all_paid_model_id_str.format(model_id=model_id)
            )

            username = profile.scrape_profile(model_id).get("username")
            if username == of_env.getattr(
                "DELETED_MODEL_PLACEHOLDER"
            ) and await check_profile_table_exists(
                model_id=model_id, username=username
            ):
                username = (
                    await get_profile_info(model_id=model_id, username=username)
                    or username
                )
            progress_updater.update_activity_count(
                total=None, description=all_paid_str.format(username=username)
            )
            log.info(f"Processing {username}_{model_id}")
            await operations.table_init_create(model_id=model_id, username=username)
            log.debug(f"Created table for {username}_{model_id}")
            temp_postcollection = PostCollection(username=username, model_id=model_id)

            all_posts = list(
                map(
                    lambda x: posts_.Post(x, model_id, username, responsetype="paid"),
                    value,
                )
            )
            temp_postcollection.add_posts(all_posts, actions=actions)
            await operations.make_post_table_changes(
                temp_postcollection.posts,
                model_id=model_id,
                username=username,
            )
            await batch_mediainsert(
                temp_postcollection.get_all_unique_media(),
                model_id=model_id,
                username=username,
                downloaded=False,
            )
            text_posts = temp_postcollection.get_posts_for_text_download()

            final_medias = temp_postcollection.get_media_for_scrape_paid()
            output[model_id] = dict(
                model_id=model_id,
                username=username,
                posts=text_posts,
                medias=final_medias,
            )
            log.debug(
                f"[bold]Paid media count {username}_{model_id}[/bold] {len(final_medias)}"
            )
            progress_updater.increment_activity_count(total=None)

        log.debug(
            f"[bold]Paid Media for all models[/bold] {sum(map(lambda x:len(x['medias']),output.values()))}"
        )
        return output


@free.space_checker
async def process_labels(model_id, username, c):
    try:
        labelled_posts_ = await labels_api.get_labels(model_id, c=c)

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
        all_output = [
            post.all_media
            for labelled_post in labelled_posts_labels
            for post in labelled_post.posts
        ]

        unlocked_output = [
            post.media
            for labelled_post in labelled_posts_labels
            for post in labelled_post.posts
        ]
        log.debug(
            f"[bold]Label media count with locked[/bold] {sum(map(lambda x:len(x),all_output))}"
        )
        log.debug(
            f"[bold]Label media count without locked[/bold] {sum(map(lambda x:len(x),unlocked_output))}"
        )

        return (
            [item for sublist in all_output for item in sublist],
            [post for ele in labelled_posts_labels for post in ele.posts],
            labels_api.API,
        )
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@run
async def process_areas(ele, model_id, username, c=None):
    try:
        username = ele.name
        postcollection = await process_tasks(model_id, username, ele, c=c)
        await batch_mediainsert(
            postcollection.get_all_unique_media(),
            model_id=model_id,
            username=username,
            downloaded=False,
        )
        return postcollection
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


def process_single_task(func):
    async def inner(sem=None):
        data = None
        await sem.acquire()
        try:
            data = await func()
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            sem.release()
        return data

    return inner


async def process_tasks(model_id, username, ele, c=None):
    tasks = []

    like_area = get_like_area()
    download_area = get_download_area()
    text_area = get_text_area()
    final_post_areas = get_final_posts_area()
    max_count = max(
        min(
            of_env.getattr("API_MAX_AREAS"),
            len(final_post_areas),
        ),
        1,
    )

    sem = asyncio.Semaphore(max_count)
    postcollection = PostCollection(username=username, model_id=model_id)

    with progress_utils.setup_api_split_progress_live():
        if "Profile" in final_post_areas:
            tasks.append(
                asyncio.create_task(
                    process_single_task(partial(process_profile, username))(sem=sem)
                )
            )
        if "Pinned" in final_post_areas:
            tasks.append(
                asyncio.create_task(
                    process_single_task(
                        partial(process_pinned_posts, model_id, username, c)
                    )(sem=sem)
                )
            )

        if "Timeline" in final_post_areas:
            tasks.append(
                asyncio.create_task(
                    process_single_task(
                        partial(process_timeline_posts, model_id, username, c=c)
                    )(sem=sem)
                )
            )
        if "Archived" in final_post_areas:
            tasks.append(
                asyncio.create_task(
                    process_single_task(
                        partial(process_archived_posts, model_id, username, c=c)
                    )(sem=sem)
                )
            )

        if "Purchased" in final_post_areas:
            tasks.append(
                asyncio.create_task(
                    process_single_task(
                        partial(process_paid_post, model_id, username, c)
                    )(sem=sem)
                )
            )
        if "Messages" in final_post_areas:
            tasks.append(
                asyncio.create_task(
                    process_single_task(
                        partial(process_messages, model_id, username, c)
                    )(sem=sem)
                )
            )

        if "Highlights" in final_post_areas:
            tasks.append(
                asyncio.create_task(
                    process_single_task(
                        partial(process_highlights, model_id, username, c)
                    )(sem=sem)
                )
            )

        if "Stories" in final_post_areas:
            tasks.append(
                asyncio.create_task(
                    process_single_task(
                        partial(process_stories, model_id, username, c)
                    )(sem=sem)
                )
            )

        if "Labels" in final_post_areas and ele.active:
            tasks.append(
                asyncio.create_task(
                    process_single_task(partial(process_labels, model_id, username, c))(
                        sem=sem
                    )
                )
            )

        if "Streams" in final_post_areas and ele.active:
            tasks.append(
                asyncio.create_task(
                    process_single_task(
                        partial(process_streamed_posts, model_id, username, c)
                    )(sem=sem)
                )
            )
    for result in asyncio.as_completed(tasks):
        try:
            posts, area = await result
            area_title = area.title()
            actions_for_this_batch = []

            if area_title in like_area:
                actions_for_this_batch.append("like")
            if area_title in download_area:
                actions_for_this_batch.append("download")
            if area_title in text_area:
                actions_for_this_batch.append("text")

            if actions_for_this_batch:
                postcollection.add_posts(posts, actions=actions_for_this_batch)
            else:
                # Optional: Log if a post area didn't match any action
                log.debug(
                    f"Posts from area '{area_title}' did not match any action criteria."
                )

        except Exception as E:
            log.debug(E)
    return postcollection
