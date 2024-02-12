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

import logging
from itertools import chain

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
import ofscraper.utils.args.areas as areas
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.system.free as free

log = logging.getLogger("shared")


@free.space_checker
def process_messages(model_id, username):
    with stdout.lowstdout():
        messages_ = messages.get_messages(
            model_id,
            username,
        )
        messages_ = list(map(lambda x: posts_.Post(x, model_id, username), messages_))
        curr = set(
            operations.get_all_messages_ids(model_id=model_id, username=username)
        )
        [
            operations.write_messages_table(
                list(filter(lambda x: x.id not in curr, messages_)),
                model_id=model_id,
                username=username,
            )
        ]

        log.debug(
            f"[bold]Messages media count with locked[/bold] {sum(map(lambda x:len(x.post_media),messages_))}"
        )
        log.debug("Removing locked messages media")
        output = []
        [output.extend(message.media) for message in messages_]
        log.debug(f"[bold]Messages media count[/bold] {len(output)}")

        operations.batch_mediainsert(
            output,
            operations.write_media_table_batch,
            model_id=model_id,
            username=username,
            downloaded=False,
        )
        # Update after database
        cache.set(
            "{model_id}_scrape_messages",
            read_args.retriveArgs().after is not None
            and read_args.retriveArgs().after != 0,
        )

        return list(filter(lambda x: isinstance(x, media.Media), output))


@free.space_checker
def process_paid_post(model_id, username):
    with stdout.lowstdout():
        paid_content = paid.get_paid_posts(username, model_id)
        paid_content = list(
            map(
                lambda x: posts_.Post(x, model_id, username, responsetype="paid"),
                paid_content,
            )
        )
        curr = set(operations.get_all_post_ids(model_id=model_id, username=username))
        operations.write_post_table(
            list(filter(lambda x: x.id not in curr, paid_content)),
            model_id=model_id,
            username=username,
        )
        output = []
        [output.extend(post.media) for post in paid_content]
        log.debug(f"[bold]Paid media count without locked[/bold] {len(output)}")

        operations.batch_mediainsert(
            output,
            operations.write_media_table_batch,
            model_id=model_id,
            username=username,
            downloaded=False,
        )

        return list(filter(lambda x: isinstance(x, media.Media), output))


@free.space_checker
def process_stories(model_id, username):
    with stdout.lowstdout():
        stories = highlights.get_stories_post(model_id)
        stories = list(
            map(
                lambda x: posts_.Post(x, model_id, username, responsetype="stories"),
                stories,
            )
        )
        curr = set(operations.get_all_stories_ids(model_id=model_id, username=username))
        operations.write_stories_table(
            list(filter(lambda x: x.id not in curr, stories)),
            model_id=model_id,
            username=username,
        )

        log.debug(
            f"[bold]Story media count[/bold] {sum(map(lambda x:len(x.post_media), stories))}"
        )
        output = []
        [output.extend(stories.media) for stories in stories]
        operations.batch_mediainsert(
            output,
            operations.write_media_table_batch,
            model_id=model_id,
            username=username,
            downloaded=False,
        )

        return list(filter(lambda x: isinstance(x, media.Media), output))


@free.space_checker
def process_highlights(model_id, username):
    with stdout.lowstdout():
        highlights_ = highlights.get_highlight_post(model_id)
        highlights_ = list(
            map(
                lambda x: posts_.Post(x, model_id, username, responsetype="highlights"),
                highlights_,
            )
        )
        curr = set(operations.get_all_stories_ids(model_id=model_id, username=username))
        operations.write_stories_table(
            list(filter(lambda x: x.id not in curr, highlights_)),
            model_id=model_id,
            username=username,
        )

        log.debug(
            f"[bold]highlight media count[/bold] {sum(map(lambda x:len(x.post_media), highlights_))}"
        )
        output = []
        [output.extend(stories.media) for stories in highlights_]
        operations.batch_mediainsert(
            output,
            operations.write_media_table_batch,
            model_id=model_id,
            username=username,
            downloaded=False,
        )

        return list(filter(lambda x: isinstance(x, media.Media), output))


@free.space_checker
def process_timeline_posts(model_id, username, individual=False):
    with stdout.lowstdout():
        timeline_posts = (
            timeline.get_timeline_media(
                model_id,
                username,
            )
            if not individual
            else timeline.get_individual_post(id)
        )
        timeline_posts = list(
            map(
                lambda x: posts_.Post(x, model_id, username, "timeline"), timeline_posts
            )
        )

        curr = set(operations.get_all_post_ids(model_id=model_id, username=username))
        operations.write_post_table(
            list(filter(lambda x: x.id not in curr, timeline_posts)),
            model_id=model_id,
            username=username,
        )
        log.debug(
            f"[bold]Timeline media count with locked[/bold] {sum(map(lambda x:len(x.post_media),timeline_posts))}"
        )
        log.debug("Removing locked timeline media")
        output = []
        [output.extend(post.media) for post in timeline_posts]
        log.debug(f"[bold]Timeline media count without locked[/bold] {len(output)}")

        operations.batch_mediainsert(
            output,
            operations.write_media_table_batch,
            model_id=model_id,
            username=username,
            downloaded=False,
        )
        operations.batch_mediainsert(
            output,
            operations.update_response_media_table,
            model_id=model_id,
            username=username,
            downloaded=False,
        )
        cache.set(
            "{model_id}_full_timeline_scrape",
            read_args.retriveArgs().after is not None,
        )
        return list(filter(lambda x: isinstance(x, media.Media), output))


@free.space_checker
def process_archived_posts(model_id, username):
    with stdout.lowstdout():
        archived_posts = archive.get_archived_media(
            model_id,
            username,
        )
        archived_posts = list(
            map(
                lambda x: posts_.Post(x, model_id, username, "archived"), archived_posts
            )
        )

        curr = set(operations.get_all_post_ids(model_id=model_id, username=username))
        operations.write_post_table(
            list(filter(lambda x: x.id not in curr, archived_posts)),
            model_id=model_id,
            username=username,
        )
        log.debug(
            f"[bold]Archived media count with locked[/bold] {sum(map(lambda x:len(x.post_media),archived_posts))}"
        )
        log.debug("Removing locked archived media")
        output = []
        [output.extend(post.media) for post in archived_posts]
        log.debug(f"[bold]Archived media count without locked[/bold] {len(output)}")

        operations.batch_mediainsert(
            output,
            operations.write_media_table_batch,
            model_id=model_id,
            username=username,
            downloaded=False,
        )
        # archived is set as post
        operations.batch_mediainsert(
            output,
            operations.update_response_media_table,
            model_id=model_id,
            username=username,
            downloaded=False,
        )
        cache.set(
            "{model_id}_full_archived_scrape",
            read_args.retriveArgs().after is not None,
        )
        return list(filter(lambda x: isinstance(x, media.Media), output))


@free.space_checker
def process_pinned_posts(model_id, username):
    with stdout.lowstdout():
        pinned_posts = pinned.get_pinned_post(model_id)
        pinned_posts = list(
            map(lambda x: posts_.Post(x, model_id, username, "pinned"), pinned_posts)
        )
        curr = set(operations.get_all_post_ids(model_id=model_id, username=username))
        operations.write_post_table(
            list(filter(lambda x: x.id not in curr, pinned_posts)),
            model_id=model_id,
            username=username,
        )
        log.debug(
            f"[bold]Pinned media count with locked[/bold] {sum(map(lambda x:len(x.post_media),pinned_posts))}"
        )
        log.debug("Removing locked pinned media")
        output = []
        [output.extend(post.media) for post in pinned_posts]
        log.debug(f"[bold]Pinned media count without locked[/bold] {len(output)}")

        operations.batch_mediainsert(
            output,
            operations.write_media_table_batch,
            model_id=model_id,
            username=username,
            downloaded=False,
        )
        operations.batch_mediainsert(
            output,
            operations.update_response_media_table,
            model_id=model_id,
            username=username,
            downloaded=False,
        )

        return list(filter(lambda x: isinstance(x, media.Media), output))


@free.space_checker
def process_profile(username) -> list:
    with stdout.lowstdout():
        user_profile = profile.scrape_profile(username)
        urls, info = profile.parse_profile(user_profile)
        profile.print_profile_info(info)
        output = []
        for count, data in enumerate(urls):
            output.append(
                media.Media(
                    {
                        "url": data["url"],
                        "type": data["mediatype"],
                        "id": data["mediaid"],
                    },
                    count,
                    posts_.Post(data, info[2], username, responsetype="profile"),
                )
            )
        return output


@free.space_checker
def process_all_paid():
    with stdout.lowstdout():
        paid_content = paid.get_all_paid_posts()
        user_dict = {}
        post_array = []
        [
            user_dict.update(
                {
                    (ele.get("fromUser", None) or ele.get("author", None) or {}).get(
                        "id"
                    ): user_dict.get(
                        (
                            ele.get("fromUser", None) or ele.get("author", None) or {}
                        ).get("id"),
                        [],
                    )
                    + [ele]
                }
            )
            for ele in paid_content
        ]
        output = []
        for model_id, value in user_dict.items():
            username = profile.scrape_profile(model_id).get("username")
            if username == "modeldeleted" and operations.check_profile_table_exists(
                model_id=model_id, username=username
            ):
                username = (
                    operations.get_profile_info(model_id=model_id, username=username)
                    or username
                )
            log.info(f"Processing {username}_{model_id}")
            operations.create_tables(model_id, username)
            operations.create_backup(model_id, username)
            log.debug(f"Created table for {username}")
            all_posts = list(
                map(
                    lambda x: posts_.Post(x, model_id, username, responsetype="paid"),
                    value,
                )
            )
            new_dict = {}
            for ele in all_posts:
                new_dict[ele.id] = ele
            new_posts = new_dict.values()
            curr = set(
                operations.get_all_post_ids(model_id=model_id, username=username) or []
            )
            operations.write_post_table(
                list(filter(lambda x: x.id not in curr, new_posts)),
                model_id=model_id,
                username=username,
            )
            temp = []
            [temp.extend(post.media) for post in new_posts]
            output.extend(temp)
            log.debug(
                f"[bold]Paid media count {username}_{model_id}[/bold] {len(temp)}"
            )
            log.debug(f"Added Paid {len(temp)} media items from {username}_{model_id}")
            post_array.extend(new_posts)

        log.debug(
            f"[bold]Paid Media for all models[/bold] {sum(map(lambda x:len(x.media),post_array))}"
        )

        return filters.filterMedia(output)


@free.space_checker
def process_labels(model_id, username):
    with stdout.lowstdout():
        labels_ = labels_api.get_labels(model_id)

        labels_ = (
            labels_
            if not read_args.retriveArgs().label
            else list(
                filter(
                    lambda x: x.get("name").lower() in read_args.retriveArgs().label,
                    labels_,
                )
            )
        )
        labelled_posts_ = labels_api.get_labelled_posts(labels_, model_id)
        labelled_posts_ = list(
            map(lambda x: labels.Label(x, model_id, username), labelled_posts_)
        )
        curr = set(operations.get_all_labels_ids(model_id=model_id, username=username))
        for labelled_post in labelled_posts_:
            operations.write_labels_table(
                labelled_post,
                list(
                    filter(
                        lambda post: (labelled_post.label_id, post.id) not in curr,
                        labelled_post.posts,
                    )
                ),
                model_id=model_id,
                username=username,
            )

        log.debug(
            f"[bold]Label media count with locked[/bold] {sum(map(lambda x:len(x),[post.post_media for labelled_post in labelled_posts_ for post in labelled_post.posts]))}"
        )
        log.debug("Removing locked messages media")
        output = [
            post.media
            for labelled_post in labelled_posts_
            for post in labelled_post.posts
        ]
        log.debug(
            f"[bold]Label media count without locked[/bold] {sum(map(lambda x:len(x),output))}"
        )

        return [item for sublist in output for item in sublist]


def process_areas(ele, model_id) -> list:
    timeline_posts_dicts = []
    pinned_post_dict = []
    archived_posts_dicts = []
    highlights_dicts = []
    messages_dicts = []
    stories_dicts = []
    purchased_dict = []
    pinned_post_dict = []
    profile_dicts = []
    labels_dicts = []

    username = ele.name
    final_post_areas = set(areas.get_download_area())
    if "Profile" in final_post_areas:
        profile_dicts = process_profile(username)
    if "Pinned" in final_post_areas:
        pinned_post_dict = process_pinned_posts(model_id, username)
    if "Timeline" in final_post_areas:
        timeline_posts_dicts = process_timeline_posts(model_id, username)
    if "Archived" in final_post_areas:
        archived_posts_dicts = process_archived_posts(model_id, username)
    if "Messages" in final_post_areas:
        messages_dicts = process_messages(model_id, username)
    if "Purchased" in final_post_areas or "All" in final_post_areas:
        purchased_dict = process_paid_post(model_id, username)
    if "Highlights" in final_post_areas:
        highlights_dicts = process_highlights(model_id, username)
    if "Stories" in final_post_areas:
        stories_dicts = process_stories(model_id, username)

    if "Labels" in final_post_areas and ele.active:
        labels_dicts = process_labels(model_id, username)

    return filters.filterMedia(
        list(
            chain(
                *[
                    profile_dicts,
                    timeline_posts_dicts,
                    pinned_post_dict,
                    purchased_dict,
                    archived_posts_dicts,
                    highlights_dicts,
                    messages_dicts,
                    stories_dicts,
                    labels_dicts,
                ]
            )
        )
    )
