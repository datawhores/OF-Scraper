import logging
import time
import datetime
from collections import OrderedDict
import csv
import arrow
from rich.table import Table
from rich import box
from humanfriendly import format_size


import ofscraper.utils.console as console

from ofscraper.db.operations_.media import (
    get_timeline_media,
    get_archived_media,
    get_messages_media,
    get_streams_media,
    get_pinned_media,
    get_highlights_media,
    get_stories_media,
    get_all_medias,
)
from ofscraper.utils.logs.other import add_other_handler
from ofscraper.utils.context.run_async import run as run_async
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
import ofscraper.main.manager as manager
import ofscraper.utils.actions as actions


class DBManager:
    def __init__(self, username, model_id, remove_keys=None):
        self.username = username
        self.model_id = model_id
        self.media = []
        self.remove_keys = remove_keys or ["link", "linked"]
        self.log = logging.getLogger("shared")

    def print_media(self):
        self.get_wanted_media()
        # allow logs to  print
        time.sleep(1.5)
        self.print_dictionary_table()
        self.write_to_csv()

    def get_wanted_media(self):
        self.get_all_media()
        self.filter_media()
        self.sort_media()
        self.get_max_post()
        self.clean_dictionaries()

    @run_async
    async def get_all_media(self):
        args = settings.get_args()
        timeline = []
        archived = []
        messages = []
        streams = []
        pinned = []
        highlights = []
        stories = []
        model_id = self.model_id
        username = self.username
        self.log.info(f"getting media for {self.username}_{self.model_id}")
        if all(
            (
                "Timeline" in args.download_area,
                "Pinned" in args.download_area,
                "Archived" in args.download_area,
                "Messages" in args.download_area,
                "Streams" in args.download_area,
                "Highlights" in args.download_area,
                "Stories" in args.download_area,
            )
        ):
            # All conditions are true, so proceed with your logic
            self.media = await get_all_medias(model_id=model_id, username=username)
        else:
            if "Timeline" in args.download_area:
                timeline = await get_timeline_media(
                    model_id=model_id, username=username
                )
            if "Pinned" in args.download_area:
                pinned = await get_pinned_media(model_id=model_id, username=username)
            if "Archived" in args.download_area:
                archived = await get_archived_media(
                    model_id=model_id, username=username
                )
            if "Messages" in args.download_area:
                messages = await get_messages_media(
                    model_id=model_id, username=username
                )
            if "Streams" in args.download_area:
                streams = await get_streams_media(model_id=model_id, username=username)
            if "Highlights" in args.download_area:
                highlights = await get_highlights_media(
                    model_id=model_id, username=username
                )
            if "Stories" in args.download_area:
                stories = await get_stories_media(model_id=model_id, username=username)
            self.media = (
                timeline + messages + archived + streams + pinned + stories + highlights
            )
            self.dedup_by_media_id()

    def filter_media(self):
        self.log.info(f"filtering media for {self.username}_{self.model_id}")
        args = settings.get_args()
        medias = self.media
        # downloaded
        if args.downloaded:
            medias = [media for media in medias if media["downloaded"]]
        elif args.downloaded is False:
            medias = [media for media in medias if not media["downloaded"]]

        # download type
        if args.protected:
            medias = [media for media in medias if "mpd" in media["link"]]
        elif args.normal:
            medias = [media for media in medias if "mpd" not in media["link"]]
        # unlocked
        if args.unlocked:
            medias = [media for media in medias if media["unlocked"]]
        elif args.unlocked is False:
            medias = [media for media in medias if not media["unlocked"]]
        # preview
        if args.preview:
            medias = [media for media in medias if media["preview"]]
        elif args.preview is False:
            medias = [media for media in medias if not media["preview"]]
        # size
        if settings.get_settings().size_max:
            medias = [
                media
                for media in medias
                if (media["size"] or 0) <= settings.get_settings().size_max
            ]
        if settings.get_settings().size_min:
            medias = [
                media
                for media in medias
                if (media["size"] or 0) >= settings.get_settings().size_min
            ]
        # length
        if settings.get_settings().length_max:
            medias = [
                media
                for media in medias
                if self._convert_seconds(media) <= settings.get_settings().length_max
            ]
        if settings.get_settings().length_min:
            medias = [
                media
                for media in medias
                if self._convert_seconds(media) >= settings.get_settings().length_min
            ]
        # date
        if settings.get_settings().posted_before:
            medias = [
                media
                for media in medias
                if arrow.get(media["posted_at"] or 0)
                <= settings.get_settings().posted_before
            ]
        if settings.get_settings().posted_after:
            medias = [
                media
                for media in medias
                if arrow.get(media["posted_at"] or 0)
                >= settings.get_settings().posted_after
            ]
        if settings.get_settings().created_after:
            medias = [
                media
                for media in medias
                if arrow.get(media["created_at"] or 0)
                >= settings.get_settings().created_after
            ]
        if settings.get_settings().created_before:
            medias = [
                media
                for media in medias
                if arrow.get(media["created_at"] or 0)
                <= settings.get_settings().created_before
            ]
        # media type
        if all(
            element in settings.get_settings().mediatypes
            for element in ["Audios", "Videos", "Images"]
        ):
            pass
        else:
            medias = [
                media
                for media in medias
                if media["media_type"] in settings.get_settings().mediatypes
            ]
        # id filters
        if args.post_id:
            medias = [media for media in medias if media["post_id"] in args.post_id]
        if args.media_id:
            medias = [media for media in medias if media["media_id"] in args.media_id]
        self.media = medias

    def get_max_post(self):
        medias = self.media
        medias = (
            medias[: settings.get_settings().max_post_count]
            if settings.get_settings().max_post_count
            else medias
        )
        self.media = medias

    def sort_media(self):
        medias = self.media
        reversed = not settings.get_settings().db_asc
        sort = settings.get_settings().db_sort
        if sort == "posted":
            medias = sorted(
                medias, key=lambda x: arrow.get(x["posted_at"] or 0), reverse=reversed
            )
        elif sort == "created":
            medias = sorted(
                medias, key=lambda x: arrow.get(x["created_at"] or 0), reverse=reversed
            )
        elif sort == "filename":
            medias = sorted(medias, key=lambda x: x["filename"] or "", reverse=reversed)
        elif sort == "postid":
            medias = sorted(medias, key=lambda x: x["post_id"], reverse=reversed)
        elif sort == "mediaid":
            medias = sorted(medias, key=lambda x: x["media_id"], reverse=reversed)
        elif sort == "size":
            medias = sorted(medias, key=lambda x: x["size"] or 0, reverse=reversed)
        elif sort == "length":
            medias = sorted(
                medias, key=lambda x: self._convert_seconds(x), reverse=reversed
            )
        self.media = medias

    def clean_dictionaries(self):
        dictionaries = self.media
        # Remove specified keys from dictionaries (if provided)
        if self.remove_keys:
            remove_keys = (
                self.remove_keys
                if isinstance(self.remove_keys, list)
                else [self.remove_keys]
            )
            for dictionary in dictionaries:
                for key in remove_keys:
                    dictionary.pop(key, None)

        # modify dictionary
        for i, dictionary in enumerate(dictionaries):
            dictionary = OrderedDict(dictionary)
            dictionary["posted_at"] = arrow.get(dictionary["posted_at"]).format(
                of_env.getattr("API_DATE_FORMAT")
            )
            dictionary["created_at"] = arrow.get(dictionary["created_at"]).format(
                of_env.getattr("API_DATE_FORMAT")
            )
            size = dictionary.pop("size", None)
            dictionary["size"] = size
            dictionary["size_human"] = format_size(size or 0)
            dictionaries[i] = dictionary

    def print_dictionary_table(self):
        """Prints a list of dictionaries as a table.

        Args:
            dictionaries: A list of dictionaries to be printed.
            remove_keys: An optional list of keys to remove from the dictionaries before printing.
        """
        log = logging.getLogger("db")
        add_other_handler(log)
        dictionaries = self.media
        if len(self.media) == 0:
            self.log.error("All media filter out")
            return
        # Get the unique keys from all dictionaries
        keys = set()
        for dictionary in dictionaries:
            keys.update(dictionary.keys())

        table = Table(title="Database Table", box=box.HEAVY_EDGE, show_lines=True)

        #  log the header row with column names
        header_row = "|".join(f"{key:^20}" for key in keys)
        value = f"|{'=' * 20}|{header_row}|{'-' * 20}|"
        log.warning(value)
        # add to table
        for key in keys:
            table.add_column(key, justify="center")

        for dictionary in dictionaries:
            # Print the data rows
            row_data = [str(dictionary.get(key, "")) for key in keys]
            row = "|".join(f"{str(value):^20}" for value in row_data)
            log.warning(f"|{' ' * 20}|{row}|{'-' * 20}|")
            # add to table
            table.add_row(*row_data)
        console.get_console().print(table)

    def dedup_by_media_id(self):
        """Deduplicates an array of dictionaries based on 'media_id'.

        Args:
            dictionaries: A list of dictionaries.

        Returns:
            A new list containing unique dictionaries based on 'media_id'.
        """

        seen_media_ids = set()
        deduped_dictionaries = []
        dictionaries = self.media
        self.log.info(f"deduping media for {self.username}_{self.model_id}")
        for dictionary in dictionaries:
            media_id = dictionary["media_id"]
            if media_id not in seen_media_ids:
                seen_media_ids.add(media_id)
            deduped_dictionaries.append(dictionary)
        self.media = deduped_dictionaries

    def write_to_csv(self):
        """
        Converts a list of dictionaries into a CSV file.

        Args:
            data (list): The list of dictionaries.
            filename (str): The name of the CSV file to be created.
        """
        if not settings.get_settings().export:
            return
        self.clean_dictionaries()
        self.write_csv()

    def write_csv(self):
        # Extract unique keys and their types
        header = []
        type_hints = {}
        for d in self.media:
            for key, value in d.items():
                if key not in header:
                    header.append(key)
                    type_hints[key] = type(value)
        # Create a CSV writer
        filename = settings.get_settings().export.with_suffix(".csv")
        filename.parent.mkdir(parents=True, exist_ok=True)
        with open(filename, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=header)

            # Write the header row, ensuring consistent order
            writer.writeheader()

            # Write the data rows, handling potential value types
            for row in self.media:
                writer.writerow(row)

    def _convert_seconds(self, dictionary):
        if not dictionary.get("duration"):
            return 0
        x = time.strptime(
            ":".join(dictionary.get("duration").split(":")[-3:]), "%H:%M:%S"
        )
        curr_sec = datetime.timedelta(
            hours=x.tm_hour, minutes=x.tm_min, seconds=x.tm_sec
        ).total_seconds()
        day_sec = int(dictionary.get("duration").split(":")[0]) * 3600
        return curr_sec + day_sec


def db():
    actions.select_areas()
    for model in manager.Manager.model_manager.get_selected_models(rescan=False):
        db_manager = DBManager(model.name, model.id)
        db_manager.print_media()
