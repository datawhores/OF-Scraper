import logging
import arrow

import ofscraper.classes.of.base as base
import ofscraper.classes.of.media as Media
import ofscraper.utils.config.data as data
import ofscraper.filters.media.filters as helpers

log = logging.getLogger("shared")


class Post(base.base):
    """
    Represents a single post from OnlyFans.
    This class holds its own data and the logic to perform detailed filtering on its media.
    Its eligibility for actions is determined externally and stored in boolean flags.
    """

    def __init__(
        self, post, model_id, username, responsetype=None, label=None, mode="download"
    ):
        super().__init__()
        self._post = post
        self._model_id = int(model_id) if model_id else None
        self._username = username
        self._responsetype = responsetype
        self._label = label

        self.is_download_candidate = False
        self.is_like_candidate = False
        self.is_text_candidate = False

        self.is_actionable_like = False

        self.like_attempted = False
        self.like_success = None

        self.text_download_attempted = False
        self.text_download_succeeded = None

        self.is_metadata_candidate = False

        self.media_for_metadata = []
        self.media_to_download = []

    # --------------------------------------------------------------------------------
    # --- Action Preparation & Marking Methods ---
    # --------------------------------------------------------------------------------

    def prepare_media_for_download(self):
        """
        Processes this post's media to determine which items are candidates
        for download, assuming this post has already been marked as a download candidate.
        """
        media = self.media
        if self.media_to_download:
            return self.media_to_download
        if not media:
            return []
        media = self._apply_media_filters(media)
        self.media_to_download = media
        return media

    def prepare_media_for_metadata(self):
        """
        Processes this post's media to determine which items are candidates
        for download, assuming this post has already been marked as a download candidate.
        """
        media = self.media
        if self.media_for_metadata:
            return self.media_for_metadata
        if not media:
            return []
        media = self._apply_media_filters(media)
        self.media_for_metadata = media
        return media

    def prepare_post_for_like(self, like_action=True):
        """
        Determines if this post is specifically actionable for a like/unlike,
        assuming this post has already been marked as a like candidate.
        """
        is_candidate = self.opened and self.responsetype in {
            "Timeline",
            "Archived",
            "Pinned",
            "Streams",
        }
        if not is_candidate:
            self.is_actionable_like = False
            return

        if like_action and not self.favorited:
            self.is_actionable_like = True
        elif not like_action and self.favorited:
            self.is_actionable_like = True
        else:
            self.is_actionable_like = False

    def mark_post_liked(self, success=True):
        """
        Updates the success status of the post after a like/unlike attempt.
        """
        self.like_attempted = True
        self.like_success = success
        if success:
            self._post["isFavorite"] = True
            self.is_actionable_like = False

    def mark_post_unliked(self, success=True):
        """
        Updates the success status of the post after a like/unlike attempt.
        """
        self.like_attempted = True
        self.like_success = success
        if success:
            self._post["isFavorite"] = False
            self.is_actionable_like = False

    def mark_like_attempt(self):
        """
        Updates the status of the post before a like/unlike attempt.
        """
        self.like_attempted = True

    def mark_text_downloaded(self, success: bool):
        """Updates the status of the post after a text download attempt."""
        self.text_download_attempted = True
        self.text_download_succeeded = success

    def mark_text_download_attempt(self):
        """Marks that a text download has been attempted."""
        self.text_download_attempted = True

    @property
    def missed_downloads(self):
        """Convenience property to see what failed to download."""
        return self.failed_downloads

    # --------------------------------------------------------------------------------
    # --- Data Access Properties (Complete) ---
    # --------------------------------------------------------------------------------

    @property
    def post_media(self):
        return self._post.get("media") or []

    @property
    def label(self):
        return self._label.capitalize() if self._label else None

    @property
    def label_string(self):
        return self.label or "None"

    @property
    def post(self):
        return self._post

    @property
    def model_id(self):
        return self._model_id

    @property
    def username(self):
        return self._username.lower() if self._username else None

    @property
    def archived(self):
        return 1 if self.post.get("isArchived") else 0

    @property
    def pinned(self):
        return 1 if self.post.get("isPinned") else 0

    @property
    def stream(self):
        return 1 if self.post.get("streamId") else 0

    @property
    def favorited(self):
        if self.post.get("isFavorite"):
            return True
        else:
            return False

    @property
    def opened(self):
        return 1 if self.post.get("isOpened") else 0

    @property
    def regular_timeline(self):
        return not self.archived and not self.pinned

    @property
    def db_sanitized_text(self):
        return self.db_cleanup(self.text)

    @property
    def file_sanitized_text(self):
        return self.file_cleanup(self.text or self.id)

    @property
    def text(self):
        return self._post.get("text")

    @property
    def db_text(self):
        return self.text if not data.get_sanitizeDB() else self.db_sanitized_text

    @property
    def title(self):
        return self._post.get("title")

    @property
    def responsetype(self):
        # Prioritize the internal explicit type if set
        if self._responsetype:
            res_type = str(self._responsetype).capitalize()
            if res_type == "Message":
                return "Messages"
            return res_type

        # Check boolean flags
        if self.pinned:
            return "Pinned"
        if self.archived:
            return "Archived"
        if self.stream:
            return "Streams"

        # Fallback to raw API response type
        raw_type = self.post.get("responseType")
        if raw_type == "post":
            return "Timeline"
        elif raw_type == "message":
            return "Messages"

        # Capitalize the raw type
        return str(raw_type).capitalize() if raw_type else "Unknown"

    @property
    def id(self):
        return self._post["id"]

    @property
    def date(self):
        return self._post.get("postedAt") or self._post.get("createdAt")

    @property
    def formatted_date(self):
        return arrow.get(self.date).format("YYYY-MM-DD hh:mm:ss")

    @property
    def value(self):
        return "free" if self.price == 0 else "paid"

    @property
    def price(self):
        return float(self.post.get("price") or 0)

    @property
    def paid(self):
        return bool(
            self.post.get("isOpen")
            or self.post.get("isOpened")
            or len(self.media) > 0
            or self.price != 0
        )

    @property
    def fromuser(self):
        if self._post.get("fromUser"):
            return int(self._post["fromUser"]["id"])
        else:
            return self._model_id

    @property
    def preview(self):
        return self._post.get("preview")

    @property
    def media(self) -> list[Media.Media]:
        """Returns a list of all viewable media objects for this post."""
        if int(self.fromuser) != int(self.model_id):
            return []
        media_items = map(
            lambda x: Media.Media(x[1], x[0], self), enumerate(self.post_media)
        )
        return list(filter(lambda x: x.canview is True, media_items))

    @property
    def all_media(self) -> list[Media.Media]:
        """Returns a list of all media objects for this post, regardless of view status."""
        return list(
            map(lambda x: Media.Media(x[1], x[0], self), enumerate(self.post_media))
        )

    @property
    def expires(self):
        return (self._post.get("expiredAt") or self._post.get("expiresAt")) is not None

    @property
    def mass(self):
        return self._post.get("isFromQueue")

    @property
    def modified_responsetype(self):
        if self.archived:
            # Check if user has a custom Archived label, otherwise default to "Archived"
            return data.get_archived_responsetype() or "Archived"
        else:
            # 1. Normalize the key to lowercase for dictionary lookup
            response_key = self.responsetype.lower()

            # 2. Handle the "Post/Posts" alias normalization
            if response_key in {"post", "posts"}:
                response_key = "timeline"

            # 3. Lookup in the lowercase config dictionary
            response = data.responsetype().get(response_key)
            # 4. Fallback: if no custom mapping exists, use the original type capitalized
            if response in (None, ""):
                return self.responsetype.capitalize()

            # 5. Return the mapped value capitalized (e.g., "messages" -> "Messages")
            return response.capitalize()

    def _apply_media_filters(self, media: list) -> list:
        """
        Private helper to run a list of media through all configured filters.
        """
        media = helpers.sort_by_date(media)
        media = helpers.mediatype_type_filter(media)
        media = helpers.posts_date_filter_media(media)
        media = helpers.temp_post_filter(media)
        media = helpers.post_text_filter(media)
        media = helpers.post_neg_text_filter(media)
        media = helpers.download_type_filter(media)
        media = helpers.mass_msg_filter(media)
        media = helpers.media_length_filter(media)
        media = helpers.media_id_filter(media)
        media = helpers.post_id_filter(media)
        return media
