import logging

from collections import defaultdict
from typing import Union
from rich.markup import escape
from ofscraper.managers.utils.state import EActivity, string_to_activity

from ofscraper.classes.of.posts import Post
from ofscraper.classes.of.media import Media

log = logging.getLogger("shared")


class MetadataStats:
    """Holds statistics for metadata update activities."""

    def __init__(self, name: str):
        self.name = name
        self.changed_video = 0
        self.changed_audio = 0
        self.changed_photo = 0
        self.unchanged_count = 0
        self.failed_count = 0

    @property
    def total_changed(self):
        return self.changed_video + self.changed_audio + self.changed_photo

    @property
    def has_changes(self):
        return self.changed_video > 0 or self.changed_audio > 0 or self.changed_photo

    def __str__(self):
        # Conditionally format the 'changed' media types
        videos_str = (
            f"[bold green]{self.changed_video} videos[/bold green]"
            if self.changed_video > 0
            else "0 videos"
        )
        audios_str = (
            f"[bold green]{self.changed_audio} audios[/bold green]"
            if self.changed_audio > 0
            else "0 audios"
        )
        photos_str = (
            f"[bold green]{self.changed_photo} photos[/bold green]"
            if self.changed_photo > 0
            else "0 photos"
        )

        # Conditionally format unchanged and failed counts
        unchanged_str = (
            f"[bold yellow]{self.unchanged_count} items unchanged[/bold yellow]"
            if self.unchanged_count > 0
            else "0 items unchanged"
        )
        failed_str = (
            f"[bold red]{self.failed_count} failed[/bold red]"
            if self.failed_count > 0
            else "0 failed"
        )

        return (
            f"({self.total_changed} changed media item total "
            f"[{videos_str}, {audios_str}, {photos_str}], "
            f"{unchanged_str}, {failed_str})"
        )


class TextStats:
    """Holds statistics for text download activities."""

    def __init__(self, name: str):
        self.name = name
        self.text_count = 0
        self.skipped_count = 0
        self.failed_count = 0

    def __str__(self):
        # Apply formatting only if the count > 0
        text_str = (
            f"[bold green]{self.text_count} text[/bold green]"
            if self.text_count > 0
            else f"{self.text_count} text"
        )
        skipped_str = (
            f"[bold yellow]{self.skipped_count} skipped[/bold yellow]"
            if self.skipped_count > 0
            else f"{self.skipped_count} skipped"
        )
        failed_str = (
            f"[bold red]{self.failed_count} failed[/bold red]"
            if self.failed_count > 0
            else f"{self.failed_count} failed"
        )
        return f"\[{text_str}, {skipped_str}, {failed_str}]"

    @property
    def has_changes(self):
        return self.text_count > 0 or self.skipped_count > 0 or self.failed_count > 0


class DownloadStats:
    """Holds statistics for download-related activities."""

    def __init__(self, name: str):
        self.name = name
        self.total_bytes = 0
        self.video_count = 0
        self.audio_count = 0
        self.photo_count = 0
        self.skipped_count = 0
        self.failed_count = 0

    @property
    def total_count(self):
        return self.video_count + self.audio_count + self.photo_count

    @property
    def has_changes(self):
        return self.total_count > 0 or self.skipped_count > 0 or self.failed_count > 0

    def __str__(self):
        # Format size
        if self.total_bytes > 1024 * 1024 * 1024:
            size_str = f"{self.total_bytes / (1024**3):.2f} GB"
        else:
            size_str = f"{self.total_bytes / (1024**2):.2f} MB"

        # Apply formatting conditionally
        size_str = f"[bold]{size_str}[/bold]" if self.total_bytes > 0 else size_str
        videos_str = (
            f"[bold green]{self.video_count} videos[/bold green]"
            if self.video_count > 0
            else f"{self.video_count} videos"
        )
        audios_str = (
            f"[bold green]{self.audio_count} audios[/bold green]"
            if self.audio_count > 0
            else f"{self.audio_count} audios"
        )
        photos_str = (
            f"[bold green]{self.photo_count} photos[/bold green]"
            if self.photo_count > 0
            else f"{self.photo_count} photos"
        )
        skipped_str = (
            f"[bold yellow]{self.skipped_count} skipped[/bold yellow]"
            if self.skipped_count > 0
            else f"{self.skipped_count} skipped"
        )
        failed_str = (
            f"[bold red]{self.failed_count} failed[/bold red]"
            if self.failed_count > 0
            else f"{self.failed_count} failed"
        )
        downloads_str = (
            f"[bold]{self.total_count} downloads total[/bold]"
            if self.has_changes
            else f"{self.total_count} downloads total"
        )
        return (
            f"({size_str}) ({downloads_str} "
            f"\[{videos_str}, {audios_str}, {photos_str}], "
            f"{skipped_str}, {failed_str})"
        )


class LikeStats:
    """Holds statistics for liking/unliking posts."""

    def __init__(self, name: str):
        self.name = name
        self.posts_checked = 0
        self.posts_liked = 0
        self.posts_unliked = 0
        self.posts_failed = 0

    @property
    def posts_changed(self):
        return self.posts_liked + self.posts_unliked

    @property
    def posts_unchanged(self):
        return self.posts_checked - self.posts_changed - self.posts_failed

    @property
    def has_changes(self):
        return self.posts_changed > 0 or self.posts_failed > 0

    def __str__(self):
        # Apply formatting conditionally
        liked_str = (
            f"[bold green]{self.posts_liked} liked[/bold green]"
            if self.posts_liked > 0
            else f"{self.posts_liked} liked"
        )
        unliked_str = (
            f"[bold green]{self.posts_unliked} unliked[/bold green]"
            if self.posts_unliked > 0
            else f"{self.posts_unliked} unliked"
        )
        failed_str = (
            f"[bold red]{self.posts_failed} failed[/bold red]"
            if self.posts_failed > 0
            else f"{self.posts_failed} failed"
        )
        unchanged_str = (
            f"[bold]{self.posts_unchanged} unchanged[/bold]"
            if self.posts_unchanged > 0
            else f"{self.posts_unchanged} unchanged"
        )
        checked_str = (
            f"[bold]{self.posts_checked} posts checked[/bold]"
            if self.posts_checked > 0
            else f"{self.posts_checked} posts checked"
        )
        return (
            f"[{checked_str}, "
            f"({liked_str}, {unliked_str}), "
            f"{unchanged_str}, {failed_str}]"
        )


class StatsManager:
    def __init__(self):
        # Using defaultdict simplifies adding new users and activities.
        # Structure: {username: {activity_enum: StatObject}}
        self._stats = defaultdict(dict)

    def update_stats(
        self, username: str, activity: Union[str, EActivity], data_list: list
    ):
        """
        A unified entry point to update stats for any activity.
        It dispatches the data to the correct internal update method.
        """
        # Get or create the stat object first
        stat_obj = self._get_stat_obj(username, activity)
        activity_enum = (
            string_to_activity(activity) if isinstance(activity, str) else activity
        )

        # Dispatch to the correct private helper based on the activity type
        if activity_enum in [
            EActivity.ScrapeActivity.DOWNLOAD,
            EActivity.PaidActivity.SCRAPE_PAID_DOWNLOAD,
        ]:
            self._update_download_stats_helper(stat_obj, data_list)
        elif activity_enum in [
            EActivity.ScrapeActivity.LIKE,
            EActivity.ScrapeActivity.UNLIKE,
        ]:
            self._update_like_stats_helper(stat_obj, data_list)
        elif activity_enum == EActivity.ScrapeActivity.TEXT:
            self._update_text_stats_helper(stat_obj, data_list)
        elif activity_enum in [
            EActivity.ScrapeActivity.METADATA,
            EActivity.PaidActivity.SCRAPE_PAID_METADATA,
        ]:
            self._update_metadata_stats_helper(stat_obj, data_list)

    def update_and_print_stats(
        self,
        username: str,
        activity: Union[str, EActivity],
        data_list: list,
        ignore_missing=False,
    ):
        """
        A convenience method that updates the stats for an activity and then
        immediately prints the summary for that specific activity.
        """
        # Step 1: Call the unified update method to process the data
        self.update_stats(username, activity, data_list)

        # Step 2: Immediately call the print method for that same activity
        self.print_user_activity_summary(
            username, activity, ignore_missing=ignore_missing
        )

    def print_all_summary(self):
        """Builds a complete summary string grouped by user and logs it once."""
        if not self._stats:
            return

        summary_string = "".join(
            self._get_user_summary_string(username)
            for username in sorted(self._stats.keys())
        )

        if summary_string:
            log.error("\n\n--- Final Stats Summary ---" + summary_string)

    def print_summary_by_activity(self):
        """Builds a complete summary string grouped by activity and logs it once."""
        if not self._stats:
            return

        stats_by_activity = defaultdict(list)
        for username, activity_dict in self._stats.items():
            for activity, stat_obj in activity_dict.items():
                # We no longer filter here; we include all stats
                stats_by_activity[activity].append((username, stat_obj))

        if not stats_by_activity:
            return

        output_lines = ["\n\n--- Final Stats Summary  ---"]
        for activity in sorted(stats_by_activity.keys(), key=lambda x: x.name):
            user_stat_list = stats_by_activity[activity]

            activity_header = escape(user_stat_list[0][1].name)
            output_lines.append(f"\n--- {activity_header} ---")

            for username, stat_obj in sorted(user_stat_list, key=lambda x: x[0]):
                prefix = escape(f"[{username}][{stat_obj.name}]")
                # Conditionally apply bolding
                formatted_prefix = (
                    f"[bold]{prefix}[/bold]" if stat_obj.has_changes else prefix
                )
                output_lines.append(f"{formatted_prefix} {stat_obj}")

        log.error("\n".join(output_lines))

    def print_user_activity_summary(
        self, username: str, activity: Union[str, EActivity], ignore_missing=False
    ):
        """
        Prints a formatted summary for a single activity for a specific user.
        The prefix is bolded only if there are non-zero stats.
        """
        try:
            activity_enum = (
                string_to_activity(activity) if isinstance(activity, str) else activity
            )
            stat_obj = self._stats[username][activity_enum]

            # Create the plain prefix first
            prefix = escape(f"[{username}][{stat_obj.name}]")

            # Conditionally apply bolding based on the has_changes property
            formatted_prefix = (
                f"[bold]{prefix}[/bold]" if stat_obj.has_changes else prefix
            )

            # Build the final output string and log it once
            output_string = f"{formatted_prefix} {stat_obj}\n"
            log.error(output_string)

        except KeyError as err:
            if not ignore_missing:
                raise KeyError(
                    f"No statistics found for user '{username}' and activity '{activity}'."
                ) from err

    def clear_scraper_activity_stats(self):
        """
        Removes all stat entries for any activity that is a ScrapeActivity
        across all users, while leaving other activity types untouched.
        """
        # Iterate through all users
        for username in list(self._stats.keys()):
            user_activities = self._stats[username]
            # 1. Find all keys that need to be deleted for this user
            keys_to_delete = [
                activity_enum
                for activity_enum in user_activities
                if isinstance(activity_enum, EActivity.ScrapeActivity)
            ]
            # 2. Safely delete those keys
            for key in keys_to_delete:
                del user_activities[key]
        log.info("All Scrape Activity statistics have been cleared.")

    def clear_paid_stats(self):
        """
        Removes all stat entries for any activity that is a ScrapeActivity
        across all users, while leaving other activity types untouched.
        """
        # Iterate through all users
        for username in list(self._stats.keys()):
            user_activities = self._stats[username]
            # 1. Find all keys that need to be deleted for this user
            keys_to_delete = [
                activity_enum
                for activity_enum in user_activities
                if isinstance(activity_enum, EActivity.PaidActivity)
            ]

            # 2. Safely delete those keys
            for key in keys_to_delete:
                del user_activities[key]

        log.info("All Scrape Activity statistics have been cleared.")

    def clear_activity_stats(self, activity: Union[str, EActivity]):
        """
        Removes all stat entries for a specific activity across all users.
        This is useful for resetting counters before a new run.
        """
        # Convert the activity string to an enum for consistent key lookup
        activity_enum = (
            string_to_activity(activity) if isinstance(activity, str) else activity
        )

        # Iterate through all users in the stats dictionary
        for username in list(self._stats.keys()):
            # Use .pop() to safely remove the key if it exists
            self._stats[username].pop(activity_enum, None)

    def clear_all_stats(self):
        """
        Resets all statistics for all users and all activities.
        """
        self._stats = defaultdict(dict)
        log.debug("All statistics have been cleared.")

    def _update_download_stats_helper(
        self, stat_obj: DownloadStats, media_list: list[Media]
    ):
        """Private helper to update download stats."""
        for media in media_list:
            if not media.download_attempted:
                stat_obj.skipped_count += 1
            elif not media.download_succeeded:
                stat_obj.failed_count += 1
            else:
                stat_obj.total_bytes += media.size or 0
                mtype = media.mediatype.lower()
                if mtype == "videos":
                    stat_obj.video_count += 1
                elif mtype == "audios":
                    stat_obj.audio_count += 1
                elif mtype == "images":
                    stat_obj.photo_count += 1

    def _update_like_stats_helper(self, stat_obj: LikeStats, post_list: list[Post]):
        """Private helper to update like stats."""
        for post in post_list:
            stat_obj.posts_checked += 1
            if post.favorited and post.like_success:
                stat_obj.posts_liked += 1
            elif not post.favorited and post.like_success:
                stat_obj.posts_unliked += 1
            elif not post.like_success:
                stat_obj.posts_failed += 1

    def _update_text_stats_helper(self, stat_obj: TextStats, post_list: list[Post]):
        """Private helper to update text download stats."""
        for post in post_list:
            if not post.text_download_attempted:
                stat_obj.skipped_count += 1
            elif not post.text_download_succeeded:
                stat_obj.failed_count += 1
            else:
                stat_obj.text_count += 1

    def _update_metadata_stats_helper(
        self, stat_obj: MetadataStats, media_list: list[Media]
    ):
        """Private helper that contains the loop logic for metadata stats."""
        for media in media_list:
            if not media.metadata_attempted:
                stat_obj.skipped_count += 1
            elif media.metadata_succeeded is False:
                stat_obj.failed_count += 1
            elif media.metadata_succeeded is True:  # Changed
                mtype = media.mediatype.lower()
                if mtype == "videos":
                    stat_obj.changed_video += 1
                elif mtype == "audios":
                    stat_obj.changed_audio += 1
                elif mtype == "images":
                    stat_obj.changed_photo += 1
            elif media.metadata_succeeded is None:  # Unchanged
                stat_obj.unchanged_count += 1

    def _get_user_summary_string(self, username: str) -> str:
        if username not in self._stats:
            return ""
        lines = []

        for stat_obj in self._stats[username].values():
            prefix = escape(f"[{username}][{stat_obj.name}]")
            # Conditionally apply bolding based on the has_changes property
            formatted_prefix = (
                f"[bold]{prefix}[/bold]" if stat_obj.has_changes else prefix
            )
            lines.append(f"{formatted_prefix} {stat_obj}")
        return "\n".join(lines) if len(lines) > 1 else ""

    def _get_stat_obj(self, username: str, activity: Union[str, EActivity]):
        """
        Internal factory that gets or creates the correct stat object
        for any given activity.
        """
        activity_enum = (
            string_to_activity(activity) if isinstance(activity, str) else activity
        )

        if activity_enum not in self._stats[username]:
            activity_name = activity_enum.name.title()

            # Route to the correct Stat class based on the enum member
            if activity_enum in [
                EActivity.ScrapeActivity.METADATA,
                EActivity.PaidActivity.SCRAPE_PAID_METADATA,
            ]:
                self._stats[username][activity_enum] = MetadataStats(
                    name=f"Action {activity_name}"
                )
            elif activity_enum == EActivity.ScrapeActivity.TEXT:
                self._stats[username][activity_enum] = TextStats(
                    name="Action Text Download"
                )
            elif activity_enum in [
                EActivity.ScrapeActivity.LIKE,
                EActivity.ScrapeActivity.UNLIKE,
            ]:
                self._stats[username][activity_enum] = LikeStats(
                    name=f"Action {activity_name}d"
                )
            else:  # Default for DOWNLOAD and SCRAPE_PAID_DOWNLOAD
                self._stats[username][activity_enum] = DownloadStats(
                    name=f"Action {activity_name}"
                )

        return self._stats[username][activity_enum]
