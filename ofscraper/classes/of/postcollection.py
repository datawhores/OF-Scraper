import logging
import ofscraper.filters.media.filters as helpers
import ofscraper.utils.settings as settings
from ofscraper.classes.of.posts import Post

log = logging.getLogger("shared")


class PostCollection:
    """
    Manages a de-duplicated collection of Post objects. It orchestrates
    the filtering and preparation of posts and their media for various actions.
    """

    def __init__(self, model_id=None, username=None, mode="download"):
        """
        Initializes an empty collection for posts.

        Args:
            model_id (int, optional): The model's ID. Defaults to None.
            username (str, optional): The model's username. Defaults to None.
            mode (str, optional): The operating mode ('download' or 'metadata'). Defaults to 'download'.
        """
        self.username = username
        self.model_id = model_id
        self.mode = mode
        # Internal dictionary to store posts, using post_id as the key for de-duplication
        self._posts_map = {}
        log.info(f"Initialized PostCollection for {username}")

    @property
    def posts(self) -> list[Post]:
        """Returns a list of the unique Post objects in the collection."""
        return list(self._posts_map.values())

    @property
    def all_media(self) -> list:
        """
        Collects EVERY media item from EVERY post in the collection,
        regardless of filtering. This is useful for creating a master list.
        """
        return [media for post in self.posts for media in post.all_media]

    def get_media_by_types(self, mediatypes: list[str] or str) -> list:
        """
        Filters all media in the collection by one or more media types.

        Args:
            mediatypes (list[str] or str): A string (e.g., 'videos') or a list of strings
                                        (e.g., ['images', 'gifs']) to filter by.

        Returns:
            list: A flat list of all Media objects that match the given type(s).
        """
        if isinstance(mediatypes, str):
            mediatypes = [mediatypes]

        # Use a set for efficient lookup, and normalize to lowercase for robust matching
        target_types = {t.lower() for t in mediatypes}

        all_media = self.all_media  # Use the existing property to get all media

        # Return a new list containing only media of the matching types
        return [media for media in all_media if media.mediatype.lower() in target_types]

    def get_all_unique_media(self) -> list:
        """
        Takes ALL media from the collection and applies a specific, short
        sequence of download-related filters.

        Returns:
            list: A list of unique Media objects.
        """
        log.info("Filtering all media with specific download filter sequence...")

        # Start with every piece of media in the collection
        media_to_filter = self.all_media

        # Apply the exact filter sequence you requested
        filtered_media = helpers.dupefiltermedia(media_to_filter)
        log.info(f"Returning {len(filtered_media)} items after specific filtering.")
        return filtered_media

    def add_posts(self, posts_or_data_list: list, actions: list[str] = None):
        """
        Adds a list of items to the collection, handling both raw dictionaries
        and existing Post objects, while ignoring any duplicates. It marks posts
        as candidates for actions based on the provided context.

        Args:
            posts_or_data_list (list): A list containing either raw post dicts or Post objects.
            actions (list[str], optional): List of actions ('like', 'download', 'text')
                                           this batch is eligible for. Defaults to None.
        """
        actions = actions or []
        if not posts_or_data_list:
            return

        new_posts_added = 0
        for item in posts_or_data_list:
            post_object, post_id = (
                (item, item.id) if isinstance(item, Post) else (None, item.get("id"))
            )
            if not post_id:
                log.warning(f"Skipping an item because it's missing an 'id': {item}")
                continue

            if post_id not in self._posts_map:
                post_object = post_object or Post(
                    item, self.model_id, self.username, mode=self.mode
                )
                self._posts_map[post_id] = post_object
                new_posts_added += 1

            # Get the single source of truth from the map
            existing_post = self._posts_map[post_id]

            # Set eligibility flags based on the context provided
            if "like" in actions:
                existing_post.is_like_candidate = True
            if "download" in actions:
                existing_post.is_download_candidate = True
            if "text" in actions:
                existing_post.is_text_candidate = True

        if new_posts_added > 0:
            log.info(f"Added {new_posts_added} new, unique posts to the collection.")

    def _get_prepared_media_from_candidates(self) -> list:
        """
        Private helper to get download candidates, run per-post filtering,
        and return the aggregated list of media before final filtering.
        """
        candidate_posts = [post for post in self.posts if post.is_download_candidate]
        log.info(f"Found {len(candidate_posts)} posts marked as download candidates.")

        for post in candidate_posts:
            post.prepare_media_for_download()

        all_media = [
            media for post in candidate_posts for media in post.media_to_download
        ]
        log.debug(f"Aggregated {len(all_media)} media items before final filtering.")
        return all_media

    def get_media_to_download(self) -> list:
        """
        Gets the final, filtered list of media for DOWNLOAD mode.
        """
        filtersettings = settings.get_settings().mediatypes
        log.debug(f"filtering Media to {','.join(filtersettings)}")

        all_media = self._get_prepared_media_from_candidates()

        log.info("Applying final 'download' mode filters to media list...")
        all_media = helpers.dupefiltermedia(all_media)
        all_media = helpers.previous_download_filter(
            all_media, username=self.username, model_id=self.model_id
        )
        all_media = helpers.ele_count_filter(all_media)
        all_media = helpers.final_media_sort(all_media)

        log.info(f"Returning {len(all_media)} final media items for download.")
        return all_media

    def get_media_for_metadata(self) -> list:
        """
        Gets the final, filtered list of media for METADATA mode.
        """
        all_media = self._get_prepared_media_from_candidates()

        log.info("Applying final 'metadata' mode filters to media list...")
        all_media = helpers.previous_download_filter(
            all_media, username=self.username, model_id=self.model_id
        )
        all_media = helpers.ele_count_filter(all_media)
        all_media = helpers.final_media_sort(all_media)

        log.info(f"Returning {len(all_media)} final media items for metadata.")
        return all_media

    def get_media_for_scrape_paid(self):
        if settings.get_settings().command == "metadata":
            return self.get_media_for_metadata()
        else:
            return self.get_media_to_download()

    def get_posts_to_like(self) -> list[Post]:
        """
        Gets the final, filtered list of posts to be liked. This method is now
        self-contained and includes the full preparation and filtering pipeline.
        """
        # 1. Determine the action type ('like' or 'unlike') from settings.
        like_action = None
        if "like" in settings.get_settings().action:
            like_action = True
        elif "unlike" in settings.get_settings().action:
            like_action = False
        else:
            # If neither action is specified, there's nothing to do.
            log.debug("Skipping like filtering because 'like' or 'unlike' not in actions.")
            return []

        like_candidates = [post for post in self.posts if post.is_like_candidate]
        log.info(f"Found {len(like_candidates)} posts in areas eligible for liking.")
        
        actionable_posts = []
        for post in like_candidates:
            post.prepare_post_for_like(like_action=like_action)
            if post.is_actionable_like:
                actionable_posts.append(post)
        log.debug(f"{len(actionable_posts)} posts are actionable for liking.")
        
        final_posts_to_like = helpers.sort_by_date(actionable_posts)
        final_posts_to_like = helpers.dupefilterPost(final_posts_to_like)
        final_posts_to_like = helpers.temp_post_filter(final_posts_to_like)
        final_posts_to_like = helpers.final_post_sort(final_posts_to_like)
        
        log.info(f"Returning {len(final_posts_to_like)} final posts to be liked.")
        return final_posts_to_like
    def get_posts_for_text_download(self) -> list[Post]:
        """
        Filters the list of text candidates to get the final list of posts
        whose text should be downloaded.
        """
        if "download" not in settings.get_settings().action:
            return []
        if not settings.get_download_text():
            return []

        text_candidates = [post for post in self.posts if post.is_text_candidate]
        log.info(
            f"Found {len(text_candidates)} posts in areas eligible for text download."
        )

        posts_for_text = helpers.sort_by_date(text_candidates)
        posts_for_text = helpers.dupefilterPost(posts_for_text)
        posts_for_text = helpers.temp_post_filter(posts_for_text)
        posts_for_text = helpers.post_text_filter(posts_for_text)
        posts_for_text = helpers.post_neg_text_filter(posts_for_text)
        posts_for_text = helpers.mass_msg_filter(posts_for_text)
        posts_for_text = helpers.final_post_sort(posts_for_text)

        log.info(
            f"Found {len(posts_for_text)} posts for text download after final filtering."
        )
        return posts_for_text
