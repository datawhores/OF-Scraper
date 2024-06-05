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
import ofscraper.db.operations as operations
import ofscraper.filters.media.main as filters
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.system.free as free
import ofscraper.utils.system.system as system
from ofscraper.commands.helpers.strings import all_paid_model_id_str, all_paid_str
from ofscraper.db.operations_.media import batch_mediainsert
from ofscraper.db.operations_.profile import (
    check_profile_table_exists,
    get_profile_info,
)
from ofscraper.utils.args.helpers.areas import (
    get_download_area,
    get_final_posts_area,
    get_like_area,
)
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")


@run
async def post_media_process(ele, c=None):

    username = ele.name
    model_id = ele.id
    console.get_shared_console().clear()
    console.get_shared_console().clear_live()
    await operations.table_init_create(model_id=model_id, username=username)
    data = await process_areas(ele, model_id, username, c=c)
    return data




@free.space_checker
async def process_messages(model_id, username, c):
    try:
        messages_ = await messages.get_messages(model_id, username, c=c)
        messages_ = list(map(lambda x: posts_.Post(x, model_id, username), messages_))
        await operations.make_messages_table_changes(
            messages_,
            model_id=model_id,
            username=username,
        )
        all_output = [item for message in messages_ for item in message.all_media]
        unlocked = [item for message in messages_ for item in message.media]
        log.debug(f"[bold]Messages media count with locked[/bold] {len(all_output)}")
        log.debug(f"[bold]Messages media count without locked[/bold] {len(unlocked)}")

        # Update after database
        cache.set(
            f"{model_id}_scrape_messages",
            read_args.retriveArgs().after is not None
            and read_args.retriveArgs().after != 0,
        )

        return all_output, messages_, "Messages"
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
        all_output = [item for post in paid_content for item in post.all_media]
        unlocked = [item for post in paid_content for item in post.media]
        log.debug(f"[bold]Paid media count with locked[/bold] {len(all_output)}")
        log.debug(f"[bold]Paid media count without locked[/bold] {len(unlocked)}")

        return (all_output, paid_content, "Purchased")
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_stories(model_id, username, c):
    try:
        stories = await highlights.get_stories_post(model_id, c=c)
        stories = list(
            map(
                lambda x: posts_.Post(x, model_id, username, responsetype="stories"),
                stories,
            )
        )
        await operations.make_stories_table_changes(
            stories,
            model_id=model_id,
            username=username,
        )
        all_output = [item for post in stories for item in post.all_media]
        unlocked = [item for post in stories for item in post.media]
        log.debug(f"[bold]Stories media count with locked[/bold] {len(all_output)}")
        log.debug(f"[bold]Stories media count without locked[/bold] {len(unlocked)}")

        return all_output, stories, "Stories"
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_highlights(model_id, username, c):
    try:
        highlights_ = await highlights.get_highlight_post(model_id, c=c)
        highlights_ = list(
            map(
                lambda x: posts_.Post(x, model_id, username, responsetype="highlights"),
                highlights_,
            )
        )
        await operations.make_stories_table_changes(
            highlights_,
            model_id=model_id,
            username=username,
        )
        all_output = [item for post in highlights_ for item in post.all_media]
        unlocked = [item for post in highlights_ for item in post.media]

        log.debug(f"[bold]Highlights media count with locked[/bold] {len(all_output)}")
        log.debug(f"[bold]Highlights media count without locked[/bold] {len(unlocked)}")

        return (all_output, highlights_, "Highlights")
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_timeline_posts(model_id, username, c):
    try:
        timeline_posts = await timeline.get_timeline_posts(model_id, username, c=c)

        timeline_posts = list(
            map(
                lambda x: posts_.Post(x, model_id, username, "timeline"),
                timeline_posts,
            )
        )
        timeline_only_posts = list(filter(lambda x: x.regular_timeline, timeline_posts))

        await operations.make_post_table_changes(
            timeline_only_posts,
            model_id=model_id,
            username=username,
        )
        all_output = [item for post in timeline_only_posts for item in post.all_media]
        unlocked = [item for post in timeline_only_posts for item in post.media]
        log.debug(f"[bold]Timeline media count with locked[/bold] {len(all_output)}")
        log.debug(f"[bold]Timeline media count without locked[/bold] {len(unlocked)}")
        cache.set(
            f"{model_id}_full_timeline_scrape",
            read_args.retriveArgs().after is not None,
        )
        log.debug("Returning timeline results")
        return (all_output, timeline_only_posts, "Timeline")
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_archived_posts(model_id, username, c):
    try:
        archived_posts = await archive.get_archived_posts(model_id, username, c=c)
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

        all_output = [item for post in archived_posts for item in post.all_media]
        unlocked = [item for post in archived_posts for item in post.media]
        log.debug(f"[bold]Archived media count with locked[/bold] {len(all_output)}")
        log.debug(f"[bold]Archived media count without locked[/bold] {len(unlocked)}")

        cache.set(
            f"{model_id}_full_archived_scrape",
            read_args.retriveArgs().after is not None,
        )
        return (all_output, archived_posts, "archived")
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_pinned_posts(model_id, username, c):
    try:
        pinned_posts = await pinned.get_pinned_posts(model_id, c=c)
        pinned_posts = list(
            map(lambda x: posts_.Post(x, model_id, username), pinned_posts)
        )
        await operations.make_post_table_changes(
            pinned_posts,
            model_id=model_id,
            username=username,
        )

        all_output = [item for post in pinned_posts for item in post.all_media]
        unlocked = [item for post in pinned_posts for item in post.media]
        log.debug(f"[bold]Pinned media count with locked[/bold] {len(all_output)}")
        log.debug(f"[bold]Pinned media count without locked[/bold] {len(unlocked)}")

        return (all_output, pinned_posts, "Pinned")
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())


@free.space_checker
async def process_profile(username) -> list:
    try:
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
        return output, posts, "Profile"
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
        progress_utils.update_activity_task(description="Processsing Paid content data")
        for model_id, value in paid_content.items():
            progress_utils.update_activity_count(
                total=None, description=all_paid_model_id_str.format(model_id=model_id)
            )

            username = profile.scrape_profile(model_id, refresh=False).get("username")
            if username == constants.getattr(
                "DELETED_MODEL_PLACEHOLDER"
            ) and await check_profile_table_exists(
                model_id=model_id, username=username
            ):
                username = (
                    await get_profile_info(model_id=model_id, username=username)
                    or username
                )
            progress_utils.update_activity_count(
                total=None, description=all_paid_str.format(username=username)
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
            all_medias = [item for post in new_posts for item in post.all_media]
            insert_media = filters.filtermediaAreas(
                all_medias, model_id=model_id, username=username
            )
            new_posts = filters.filterPostFinal(new_posts)
            await operations.make_post_table_changes(
                new_posts,
                model_id=model_id,
                username=username,
            )
            await batch_mediainsert(
                insert_media,
                model_id=model_id,
                username=username,
                downloaded=False,
            )
            final_medias=filters.filtermediaFinal(insert_media)

            output[model_id] = dict(
                model_id=model_id, username=username, posts=new_posts, medias=final_medias
            )
            log.debug(
                f"[bold]Paid media count {username}_{model_id}[/bold] {len(final_medias)}"
            )
            progress_utils.increment_activity_count(total=None)

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
            "Labels",
        )
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())





@run
async def process_areas(ele, model_id, username, c=None):
    try:
        username = ele.name
        medias, posts, like_post = await process_tasks(model_id, username, ele, c=c)
        insert_medias=filters.filtermediaAreas(medias)
        await batch_mediainsert(
            insert_medias,
            model_id=model_id,
            username=username,
            downloaded=False,
        )
        return (insert_medias, posts, like_post)
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
    mediaObjs = []
    postObjs = []
    likeObjs = []
    tasks = []

    like_area = get_like_area()
    download_area = get_download_area()
    final_post_areas = get_final_posts_area()
    max_count = max(
        min(
            constants.getattr("API_MAX_AREAS"),
            system.getcpu_count(),
            len(final_post_areas),
        ),
        1,
    )

    sem = asyncio.Semaphore(max_count)

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
                        partial(process_timeline_posts, model_id, username, c)
                    )(sem=sem)
                )
            )
        if "Archived" in final_post_areas:
            tasks.append(
                asyncio.create_task(
                    process_single_task(
                        partial(process_archived_posts, model_id, username, c)
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

        for results in asyncio.as_completed(tasks):
            try:
                medias, posts, area = await results
                if area in like_area:
                    likeObjs.extend(posts or [])
                if area in download_area:
                    mediaObjs.extend(medias or [])
                    postObjs.extend(posts or [])
            except Exception as E:
                log.debug(E)
    return mediaObjs, postObjs, likeObjs
