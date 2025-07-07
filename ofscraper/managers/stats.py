from collections import defaultdict
from ofscraper.managers.utils.state import EActivity

from ofscraper.classes.of.posts import Post
from ofscraper.classes.of.media import Media


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

    def __str__(self):
        # Format size into MB or GB for readability
        if self.total_bytes > 1024 * 1024 * 1024:
            size_str = f"{self.total_bytes / (1024**3):.2f} GB"
        else:
            size_str = f"{self.total_bytes / (1024**2):.2f} MB"

        return (
            f"({size_str}) ({self.total_count} downloads total "
            f"[{self.video_count} videos, {self.audio_count} audios, {self.photo_count} photos], "
            f"{self.skipped_count} skipped, {self.failed_count} failed)"
        )


class LikeStats:
    """Holds statistics for liking/unliking posts."""

    def __init__(self, name: str):
        self.name = name
        self.posts_checked = 0
        self.posts_liked = 0  # Changed to liked
        self.posts_unliked = 0  # Changed to unliked
        self.posts_failed = 0

    @property
    def posts_changed(self):
        return self.posts_liked + self.posts_unliked

    @property
    def posts_unchanged(self):
        return self.posts_checked - self.posts_changed - self.posts_failed

    def __str__(self):
        return (
            f"[{self.posts_checked} posts checked, "
            f"({self.posts_liked} liked, {self.posts_unliked} unliked), "
            f"{self.posts_unchanged} unchanged, {self.posts_failed} failed]"
        )


class StatsManager:
    def __init__(self):
        # Using defaultdict simplifies adding new users and activities.
        # Structure: {username: {activity_enum: StatObject}}
        self._stats = defaultdict(dict)

    def _get_stat_obj(self, username: str, activity: EActivity):
        """Internal factory to get or create a stat object."""
        if activity not in self._stats[username]:
            # Create the correct stat object based on the activity type
            if "download" in activity.name.lower() or "paid" in activity.name.lower():
                self._stats[username][activity] = DownloadStats(
                    name=f"Action {activity.name.title()}"
                )
            elif "like" in activity.name.lower():
                self._stats[username][activity] = LikeStats(
                    name=f"Action {activity.name.title()}d"
                )
        return self._stats[username][activity]

    def update_download_stats(
        self, username: str, activity: EActivity, media_list: list[Media]
    ):
        """Updates download stats from a list of Media objects."""
        stat_obj = self._get_stat_obj(username, activity)
        for media in media_list:
            if not media.download_attempted:
                stat_obj.skipped_count += 1
            elif not media.download_succeeded:
                stat_obj.failed_count += 1
            else:  # Download succeeded
                stat_obj.total_bytes += media.final_size or 0
                mtype = media.mediatype
                if mtype == "videos":
                    stat_obj.video_count += 1
                elif mtype == "audios":
                    stat_obj.audio_count += 1
                elif mtype == "images":
                    stat_obj.photo_count += 1

    def update_like_stats(
        self, username: str, activity: EActivity, post_list: list[Post]
    ):
        """Updates like stats from a list of Post objects."""
        stat_obj = self._get_stat_obj(username, activity)
        for post in post_list:
            stat_obj.posts_checked += 1
            if post.like_result == "liked":
                stat_obj.posts_liked += 1
            elif post.like_result == "unliked":
                stat_obj.posts_unliked += 1
            elif post.like_result == "failed":
                stat_obj.posts_failed += 1

    def print_user_summary(self, username: str):
        """Prints a formatted summary for a single user."""
        if username not in self._stats:
            return
        print(f"\n--- {username} Final Stats ---")
        for activity, stat_obj in self._stats[username].items():
            print(f"[{username}][{stat_obj.name}] {stat_obj}")
        print("---------------------------\n")

    def print_all_summary(self):
        """Prints a formatted summary for all users."""
        if not self._stats:
            return
        print("\n\n--- Final Stats Summary ---")
        for username in sorted(self._stats.keys()):
            self.print_user_summary(username)
