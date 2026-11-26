"""Rename a creator's downloaded files to the current file_format and
dir_format, and record the new names in the database; preview unless --apply
(#764).

After file_format or dir_format is changed, the scraper saves new files under
the new names, and the files already downloaded keep their old ones. This
gives them the new names. It works offline, on one creator's user_data.db,
with no login and no download. See RENAMING_FILES.md.

- Each new name is built by the placeholder code a download uses
  (ofscraper/classes/placeholder.py), with the scraper's config.json, from
  what the database holds of the media, its post and the creator. A name
  that needs a value the database doesn't hold ({quality} of a video whose
  recorded name doesn't show it, prices, {my_username}, a count in a post
  with several media, ...) can't be made: that file is left and listed.
- With --apply each recorded file is handled on its own, by where it is:
      at the old place, new place free    renamed, rows changed
      only at the new place               rows changed ("already there")
      new place taken, or recorded by     left and listed, rows unchanged
        another row, or the new name of
        another file too
      at neither                          listed
  A file is never renamed onto anything: on Windows a rename can't replace
  a file, and elsewhere it is made with a hard link that can't either.
- An undo file, beside the database, lists every rename and row change
  before the first one is made. --undo FILE puts back what is still as this
  left it. A run that stops part way (an error, Ctrl+C) gives the files it
  renamed their old names back and saves no row. It removes the undo file
  when every file is back at its old name, and keeps it otherwise.
- While PostgreSQL is on, --apply (and --undo with --apply) is refused: the
  changes would reach only the user_data.db.
- The rows of the database are locked for the whole run and their changes
  saved together at the end. Then the old folders that were emptied are
  removed, up to the save location (rmdir: a folder that holds anything
  stays).
"""

import argparse
import asyncio
import contextlib
import json
import logging
import os
import re
import sqlite3
import stat
import sys
import uuid
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

import ofscraper.db.postgres as postgres
import ofscraper.sites as sites
from ofscraper.commands import move_creator_files as mover
from ofscraper.commands.recover_collisions import _unconfirmed

FILES_NOTICE = mover.FILES_NOTICE.replace("move_creator_files", "rename_to_format").replace(
    " To work on PostgreSQL, give --postgres and --creator in place of the file.",
    " This command doesn't work on PostgreSQL.",
)
POSTGRES_REFUSED = (
    f"PostgreSQL is on ({postgres.URL_KEY} is set), and rename_to_format only changes"
    " the user_data.db files: renaming the files would part them from their"
    " PostgreSQL rows. --apply is refused; a preview still works"
)
UNDO_VERSION = 1
TOOL = "rename_to_format"
# a value the database doesn't hold is put in a name as this mark, so a name
# that needs one is found, whichever of the placeholder code's steps it went
# through (characters from Unicode's private use area: nothing writes them)
MARK = "\ue000{}\ue001"
MARKED = re.compile("\ue000([^\ue000\ue001]*)\ue001")
# why a recorded file is left where it is
NEEDS = "the new name needs {}, which the database doesn't hold"
DIFFER = "its rows give it different new names"
TAKEN = "something is already at the new place"
RECORDED = "another row records the new place"
SAME_TARGET = "another file would get the same new name"
NOT_FOUND = "not at the old place, and not at the new one"
OTHER_SIZE = "not at the old place; the file at the new place doesn't have the size the row records"
NOT_A_FILE = "not at the old place; what is at the new place isn't a file"
OLD_NOT_A_FILE = "what is at the old place isn't a file"
MEDIA = ["rowid", "media_id", "post_id", "link", "directory", "filename", "size",
         "api_type", "media_type", "created_at", "posted_at", "downloaded", "model_id"]
# the tables a media's post can be in, by the area it came from
TEXT_TABLES = {"Messages": ["messages", "posts"], "Paid": ["posts", "messages"]}


def _marked(name):
    return MARK.format(name)


class _Unknown:
    """A value the database doesn't hold that is more than a string: any
    attribute or item of it is unknown too, and it formats as the mark."""

    def __init__(self, name):
        self._name = name

    def __format__(self, spec):
        return _marked(self._name)

    __str__ = __repr__ = lambda self: _marked(self._name)

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return self

    def __getitem__(self, key):
        return self

    def __call__(self, *args, **kwargs):
        return self


class _OfflineMe:
    """The account's own name and id, which come from the site: unknown."""

    @staticmethod
    def parse_user():
        return _marked("my_username"), _marked("my_username")

    @staticmethod
    def get_id():
        return _marked("my_id")


class _OfflineManager:
    """The creator's model object (prices, ...) comes from the site: unknown."""

    class Manager:
        class current_model_manager:
            @staticmethod
            def get_model(username):
                return _Unknown("modelObj")


def _date(value):
    """A recorded date as the app reads one: a number is seconds."""
    if value in (None, ""):
        return None
    if isinstance(value, str):
        with contextlib.suppress(ValueError):
            return float(value)
    return value


def _classes():
    """The download's own Post, Media and Placeholders, with what the
    database doesn't hold made unknown. Imported here: loading them reads
    nothing, but it takes a while, and --help shouldn't wait."""
    import ofscraper.classes.placeholder as placeholder
    import ofscraper.utils.of_env.of_env as of_env
    from ofscraper.classes.of.media import Media
    from ofscraper.classes.of.posts import Post
    from ofscraper.utils.async_cached_property import async_cached_property

    class RecordedPost(Post):
        def __init__(self, known, **kwargs):
            super().__init__(**kwargs)
            self._known = known

        @property
        def value(self):
            return super().value if "price" in self._known else _marked("value")

        @property
        def label_string(self):
            return super().label_string if "label" in self._known else _marked("label")

    class RecordedMedia(Media):
        def __init__(self, media, post, row, quality, count):
            super().__init__(media, 0, post)
            self._row = row
            self._quality = quality
            self._known_count = count
            # the download says once that an undated name uses 1970; here
            # an unknown date is marked instead
            self._undated_name_warned = True

        @property
        def mediatype(self):
            return self._row["media_type"] or _marked("mediatype")

        @property
        def mpd(self):
            link = self._row["link"] or ""
            return link if re.search(r"\.mpd(\?|$)", link) else None

        @property
        def url(self):
            return None if self.mpd else self._row["link"]

        @property
        def filename(self):
            # the name in the link; without one, it isn't known
            return super().filename if self._row["link"] else _marked("filename")

        @property
        def count(self):
            return self._known_count or _marked("count")

        @property
        def file_text(self):
            return super().file_text if "text" in self._post._known else _marked("text")

        @async_cached_property
        async def selected_quality_placeholder(self):
            if self.mediatype == "Videos":
                return self._quality or _marked("quality")
            if self.mediatype == "Audios":
                return of_env.getattr("QUALITY_UNKNOWN_DEFAULT")
            return "source" if self.mediatype == "Images" else _marked("quality")

    class RenamePlaceholders(placeholder.Placeholders):
        def add_price_variables(self, username):
            for key in ("current_price", "regular_price", "promo_price", "renewal_price"):
                self._variables[key] = _marked(key)

        async def add_main_variables(self, ele, username, model_id):
            await super().add_main_variables(ele, username, model_id)
            # the run's own arguments, not the download's
            self._variables["args"] = _Unknown("args")
            if ele.postdate is None:
                self._variables["date"] = _marked("date")
            if model_id is None:
                self._variables["model_id"] = _marked("model_id")

    return placeholder, RecordedPost, RecordedMedia, RenamePlaceholders


@contextlib.contextmanager
def _offline(placeholder):
    """The placeholder code without what reaches the site."""
    saved = placeholder.me, placeholder.manager
    placeholder.me, placeholder.manager = _OfflineMe, _OfflineManager
    try:
        yield
    finally:
        placeholder.me, placeholder.manager = saved


@contextlib.contextmanager
def scraper_settings(config=None, profile=None, site=sites.DEFAULT_SITE):
    """The scraper's settings, read from its config.json as a run with these
    options would read them. Nothing is written: a missing or broken
    config.json is refused (a run would make one, or ask)."""
    import ofscraper.utils.args.globals as global_args
    import ofscraper.utils.args.parse.commands.main as program
    import ofscraper.utils.config.file as config_file
    import ofscraper.utils.encoding as encoding
    import ofscraper.utils.logs.utils.level as level
    import ofscraper.utils.paths.common as common_paths
    import ofscraper.utils.settings as settings
    from ofscraper.utils.args.main import AutoDotDict

    # the placeholder code logs at levels the scraper adds
    level.addtrace()
    level.addtraceback()
    argv = ["--site", site]
    if config:
        argv += ["--config", str(config)]
    if profile:
        argv += ["--profile", profile]
    saved = global_args.args, settings.settings
    try:
        # the scraper's own options, parsed as its parse_args does (which
        # can only be run once in a process)
        values, command = program.program(standalone_mode=False, prog_name="OF-Scraper", args=argv)
        global_args.args = AutoDotDict(values, command=command)
        settings.settings = {}
        path = Path(common_paths.get_config_path())
        try:
            # checked as the scraper's config_context checks it (json.loads): a
            # run refuses the same files, and asks to fix them
            config_file.unwrap(json.loads(encoding.read_text_file(path)))
        except FileNotFoundError:
            raise ValueError(f"There is no config.json at {path}: the formats are read from it. Give --config") from None
        except (json.JSONDecodeError, config_file.NotAnObjectError) as error:
            raise ValueError(f"{path} can't be read ({error}). Run the scraper once to fix it") from None
        settings.update_settings()
        yield settings.get_settings()
    finally:
        global_args.args, settings.settings = saved


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _select(conn, table, wanted, where=""):
    """Rows as dicts; a column the table doesn't have reads as None."""
    have = _columns(conn, table)
    if not have:
        return []
    columns = [c if c in have or c == "rowid" else f"NULL AS {c}" for c in wanted]
    query = f"SELECT {', '.join(columns)} FROM {table}" + (f" WHERE {where}" if where else "")
    return [dict(zip(wanted, row)) for row in conn.execute(query)]


def _posts(conn, sanitized):
    """What the database holds of each post, message and story, by table
    and post id: date, price, archived and text. Text saved sanitized
    (sanitize_text) isn't the text a download names a file with."""
    found = {}
    for table in ("posts", "messages", "stories"):
        rows = _select(conn, table, ["post_id", "created_at", "price", "archived", "text"])
        found[table] = {}
        for row in rows:
            known = {"price"} if row["price"] is not None else set()
            # a story's row holds its title where it has no text; a
            # download names it by its text
            if table != "stories" and not sanitized:
                known.add("text")
            found[table][str(row["post_id"])] = (row, known)
    return found


def _quality(recorded, base, replacer):
    """The quality in a video's recorded name, where the name holds the
    file's name with its quality ({filename} writes "<name>_<quality>")."""
    import ofscraper.utils.of_env.of_env as of_env

    base = re.sub(" +", " ", base).replace(" ", replacer)
    unknown = re.escape(str(of_env.getattr("QUALITY_UNKNOWN_DEFAULT")))
    found = set(re.findall(rf"{re.escape(base)}_(source|{unknown}|\d{{3,4}})(?![0-9A-Za-z])", recorded))
    return found.pop() if len(found) == 1 else None


async def _new_paths(media, username, model_id, posts, labelled, counts, site, replacer):
    """Each media row with the path a download would now give it, or why
    it can't be made: {rowid: (path or None, why)}."""
    import ofscraper.utils.config.data as config_data
    from ofscraper.utils.config.naming_check import MEDIA_TYPES, area_type_names, type_name

    placeholder, RecordedPost, RecordedMedia, RenamePlaceholders = _classes()
    out = {}
    names = {type_name(name) for name in config_data.get_type_options()}
    # "text" is the caption files', which have no row here
    by_media_type = bool(names & (MEDIA_TYPES - {"text"}))
    # an entry for an area (or its folder name)
    by_area = bool(names and names & area_type_names())
    with _offline(placeholder):
        for row in media:
            post_id = str(row["post_id"])
            area = str(row["api_type"] or "").capitalize()
            post, known = None, set()
            for table in TEXT_TABLES.get(area, ["stories"] if area in ("Stories", "Highlights") else ["posts"]):
                if post_id in posts[table]:
                    post, known = posts[table][post_id]
                    break
            post = post or {}
            known = set(known)
            if post_id not in labelled:
                known.add("label")
            date = _date(row["posted_at"]) or _date(post.get("created_at"))
            item = {
                "id": row["post_id"],
                "postedAt": date,
                "price": post.get("price") or 0,
                "text": post.get("text"),
                "isArchived": bool(post.get("archived")) or area == "Archived",
                "media": [{}] * max(counts[post_id], 1),
            }
            recorded_post = RecordedPost(
                known, post=item, model_id=model_id, username=username, responsetype=area or None,
            )
            media_dict = {"id": row["media_id"], "createdAt": _date(row["created_at"])}
            if site == sites.FANSLY:
                media_dict["fansly"] = {"mediaId": str(row["media_id"])}
            ele = RecordedMedia(media_dict, recorded_post, row, None, 1 if counts[post_id] == 1 else None)
            if ele.mediatype == "Videos" and row["link"]:
                base = re.sub("_[a-z0-9]+$", "", ele.filename)
                ele._quality = _quality(row["filename"], ele.file_cleanup(base), replacer)
            ext = Path(row["filename"]).suffix[1:] or _marked("ext")
            try:
                names = RenamePlaceholders(ele, ext)
                await names.init(create=False)
                built = f"{names._mediadir}/{names._filename}"
                path = names.trunicated_filepath
            except Exception as error:  # a format the download couldn't use either
                out[row["rowid"]] = (None, f"the new name can't be made ({type(error).__name__}: {error})")
                continue
            missing = sorted(set(MARKED.findall(built)))
            # with no media type or area, an entry for one can't be matched,
            # so which folder the file belongs in isn't known
            if not row["media_type"] and by_media_type:
                missing = sorted(set(missing) | {"mediatype"})
            if not row["api_type"] and by_area:
                missing = sorted(set(missing) | {"response_type"})
            if missing or "\ue000" in str(path) or "\ue001" in str(path):
                values = ", ".join(f"{{{name}}}" for name in missing) or "a value"
                out[row["rowid"]] = (None, NEEDS.format(values))
                continue
            out[row["rowid"]] = (Path(path), None)
    return out


def plan(conn, settings, username=None, path_root=None):
    """What a rename would do, read from the open database `conn`: the
    report, and the files to handle as [(old, new, rows)], where `rows`
    are (rowid, directory, filename, new directory, new filename, size)."""
    import ofscraper.classes.placeholder as placeholder
    import ofscraper.utils.config.data as config_data

    if settings.naming_script:
        raise ValueError(
            "naming_script is set: a download names files with that script, and this can't"
            " run it. Remove it from config.json (or the arguments) to use this"
        )
    columns = _columns(conn, "medias")
    if not {"directory", "filename"} <= columns:
        raise ValueError("This user_data.db has no medias table with recorded files")
    names = []
    if "username" in _columns(conn, "profiles"):
        names = [(row["username"], row["last_seen_at"])
                 for row in _select(conn, "profiles", ["username", "last_seen_at"])]
    ids = {row["model_id"] for row in _select(conn, "medias", ["model_id"])} - {None}
    ids |= {row["user_id"] for row in _select(conn, "profiles", ["user_id"])} - {None}
    if len(ids) > 1:
        raise ValueError(
            "This user_data.db holds the rows of more than one creator"
            f" ({', '.join(sorted(map(str, ids)))}), so it isn't known whose files to rename"
        )
    model_id = ids.pop() if ids else None
    try:
        name, why = mover.current_name(names, model_id, username)
    except ValueError as error:
        raise ValueError(str(error).replace("--to", "--username")) from None

    media = _select(conn, "medias", MEDIA)
    counts = Counter()
    for post_id, ids_ in _by_post(media).items():
        counts[post_id] = len(ids_)
    labelled = {str(row["post_id"]) for row in _select(conn, "labels", ["post_id"])}
    recorded = [row for row in media
                if isinstance(row["directory"], str) and isinstance(row["filename"], str)
                and row["directory"].strip() and row["filename"].strip()]
    site = _site(conn)
    posts = _posts(conn, config_data.get_sanitizeDB())
    built = asyncio.run(_new_paths(
        [row for row in recorded if row["downloaded"]], name, model_id, posts, labelled, counts,
        site, settings.space_replacer or " ",
    ))

    # the save location first: it's the one the report shows
    roots = [os.path.abspath(root) for root in placeholder.media_roots()]
    result = {
        "database": None, "creator": {"site": site, "model_id": model_id}, "username": name, "why": why,
        "file_format": config_data.get_fileformat(), "dir_format": config_data.get_dirformat(),
        # the per-type formats and folders, which win over the two above
        "type_options": config_data.get_type_options(),
        "save_location": roots[0], "files": 0, "unchanged": 0, "to_rename": 0, "already_there": 0,
        "left": [], "renames": [], "renamed": 0, "rows_changed": 0, "folders_removed": [],
        "undo_file": None,
    }
    # each recorded file once, with every row that records it, however
    # they spell it on a disk that tells some spellings apart only
    key = _path_key()
    files = defaultdict(list)
    for row in recorded:
        old = mover._full(Path(row["directory"], row["filename"]), path_root)
        files[key(old)].append((old, row))
    taken_by_rows = set(files)
    planned = []
    folders = {}
    for found in sorted(files.values(), key=lambda found: min(old for old, _row in found)):
        rows = [row for _old, row in found]
        if not any(row["downloaded"] for row in rows):
            continue
        # a row of another media that records this file (downloaded = 0: a
        # collision gave its place to this one) keeps its name, and doesn't
        # say how the file is spelt
        downloaded = {row["media_id"] for row in rows if row["downloaded"]}
        spellings = sorted({old for old, row in found if row["media_id"] in downloaded})
        old = _spelt_on_disk(spellings[0], key, folders) or spellings[0]
        result["files"] += 1
        new_paths = {built[row["rowid"]] for row in rows if row["rowid"] in built}
        whys = {why for _path, why in new_paths if why}
        if whys:
            result["left"].append({"file": old, "why": "; ".join(sorted(whys))})
            continue
        if len(new_paths) != 1:
            result["left"].append({"file": old, "why": DIFFER,
                                   "new_names": sorted(str(path) for path, _ in new_paths)})
            continue
        (recorded_new, _), = new_paths
        new = os.path.abspath(recorded_new)
        if new == old and spellings == [new]:
            result["unchanged"] += 1
            continue
        changes = [(row["rowid"], row["directory"], row["filename"], str(recorded_new.parent),
                    recorded_new.name, row["size"]) for row in rows if row["media_id"] in downloaded]
        planned.append((old, new, changes))

    # a new place two files would get, or that another row records
    targets = Counter(key(new) for _old, new, _rows in planned)
    to_do = []
    for old, new, changes in planned:
        at_old, at_new = _where(old, new)
        if targets[key(new)] > 1:
            result["left"].append({"file": old, "why": SAME_TARGET, "new_place": new})
        elif key(new) in taken_by_rows and key(new) != key(old):
            result["left"].append({"file": old, "why": RECORDED, "new_place": new})
        elif at_old and not _is_file(old):
            # a folder (on a disk that doesn't tell case apart, perhaps one
            # spelt as the new name) isn't the file, and isn't moved
            result["left"].append({"file": old, "why": OLD_NOT_A_FILE})
        elif new == old and at_old:
            # the file has its new name already: only rows spell it otherwise
            result["already_there"] += 1
            to_do.append(("there", old, new, changes))
        elif at_old:
            if at_new and not _same_file(old, new):
                result["left"].append({"file": old, "why": TAKEN, "new_place": new})
                continue
            result["to_rename"] += 1
            to_do.append(("rename", old, new, changes))
        elif not at_new:
            result["left"].append({"file": old, "why": NOT_FOUND})
        elif not _is_file(new):
            result["left"].append({"file": old, "why": NOT_A_FILE, "new_place": new})
        elif {size for *_row, size in changes if size is not None} - {os.stat(new).st_size}:
            result["left"].append({"file": old, "why": OTHER_SIZE, "new_place": new})
        else:
            result["already_there"] += 1
            to_do.append(("there", old, new, changes))
    return result, to_do, roots


def _by_post(media):
    found = defaultdict(set)
    for row in media:
        found[str(row["post_id"])].add(row["media_id"])
    return found


def _site(conn):
    if "flag_name" not in _columns(conn, "schema_flags"):
        return sites.DEFAULT_SITE
    row = conn.execute("SELECT flag_value FROM schema_flags WHERE flag_name = 'site'").fetchone()
    return str(row[0]).lower() if row and row[0] else sites.DEFAULT_SITE


def _same_file(old, new):
    """The new place is the old file itself: a name that differs only in
    its letters' case on a disk that doesn't tell them apart, or a hard link
    left by a run that stopped between its two steps."""
    try:
        return os.path.samefile(old, new)
    except OSError:
        return False


def _is_file(path):
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except OSError:
        return False


def _spelt_on_disk(path, key, folders):
    """`path` with its name spelt as the disk spells it, which on a disk
    that doesn't tell case apart can differ from how a row spells it; None
    when it isn't there. `folders` keeps each folder's names once read."""
    folder = os.path.dirname(path)
    if folder not in folders:
        try:
            names = os.listdir(folder)
        except OSError:
            names = []
        spelt = defaultdict(list)
        for name in names:
            spelt[key(os.path.join(folder, name))].append(os.path.join(folder, name))
        folders[folder] = spelt
    found = folders[folder].get(key(path), [])
    return found[0] if len(found) == 1 else None


def _two_names(old, new):
    """`old` and `new`, one file, are two names of it (a hard link), not
    one name spelt two ways on a disk that doesn't tell case apart."""
    old_folder, new_folder = os.path.dirname(old), os.path.dirname(new)
    if not _same_file(old_folder, new_folder):
        return True
    if os.path.basename(old) == os.path.basename(new):
        return False
    try:
        names = os.listdir(old_folder)
    except OSError:
        return False
    return os.path.basename(old) in names and os.path.basename(new) in names


def _where(old, new):
    """Whether the file is at its old place and at its new one. On a disk
    that doesn't tell case apart, a name that differs only in case finds the
    file under either spelling: it is where the spelling of its name says."""
    at_old, at_new = os.path.lexists(old), os.path.lexists(new)
    if at_old and at_new and _same_file(old, new) and not _two_names(old, new):
        try:
            spelt_new = os.path.basename(new) in os.listdir(os.path.dirname(new))
        except OSError:
            spelt_new = False
        at_new = spelt_new and os.path.basename(new) != os.path.basename(old)
        at_old = not at_new
    return at_old, at_new


def _path_key():
    """A path as the disk tells paths apart: os.path.normcase, and lower
    case on a disk that doesn't tell case apart (macOS's, whose normcase
    keeps case). That is tried on the nearest folder that is there."""
    folds = {}

    def folds_case(folder):
        if folder not in folds:
            name, parent = os.path.basename(folder), os.path.dirname(folder)
            if parent == folder:
                folds[folder] = False
            elif name.swapcase() != name and os.path.lexists(folder):
                folds[folder] = _same_file(folder, os.path.join(parent, name.swapcase()))
            else:
                folds[folder] = folds_case(parent)
        return folds[folder]

    def key(path):
        path = os.path.normcase(path)
        return path.lower() if folds_case(os.path.dirname(path)) else path

    return key


def rename_file(old, new):
    """Rename `old` to `new`, which must be free: nothing is replaced."""
    os.makedirs(os.path.dirname(new), exist_ok=True)
    if _same_file(old, new):
        if _two_names(old, new):
            # the link a stopped run made: the file is at its new place too
            # (a rename of one name onto another of the same file does nothing)
            os.unlink(old)
        else:
            # only the case changes: the same file under its new name
            os.rename(old, new)
        return
    if os.name == "nt" or os.path.islink(old):
        if os.path.lexists(new):
            raise FileExistsError(_is_there(new))
        # Windows doesn't rename onto a file
        os.rename(old, new)
        return
    try:
        # a hard link isn't made where something is
        os.link(old, new)
    except FileExistsError:
        raise
    except OSError:
        # a disk without hard links (some shares): a rename, having seen
        # the place free just before
        if os.path.lexists(new):
            raise FileExistsError(_is_there(new)) from None
        os.rename(old, new)
        return
    try:
        os.unlink(old)
    except OSError:
        # the file is left with its old name only
        if os.path.lexists(old):
            with contextlib.suppress(OSError):
                os.unlink(new)
        raise


def _is_there(path):
    return f"{path} is there already"


def _remove_emptied(moved, *roots):
    """Remove the old folders the renames left empty, up to the root they
    are in: the save location or a type_options one. A root is never
    removed, also when it's inside another one."""
    removed = []
    for old in sorted({os.path.dirname(old) for old in moved}, key=len, reverse=True):
        folder = old
        while not any(_same_folder(folder, root) for root in roots) and any(
            _inside(folder, root) for root in roots
        ):
            try:
                os.rmdir(folder)
            except OSError:
                break
            removed.append(folder)
            folder = os.path.dirname(folder)
    return removed


def _inside(folder, root):
    """`folder` is in `root`, at any depth: on another drive it isn't, and
    a disk that doesn't tell case apart finds `root` however it is spelt."""
    parent = os.path.dirname(folder)
    while parent != folder:
        if _same_folder(parent, root):
            return True
        folder, parent = parent, os.path.dirname(parent)
    return False


def _same_folder(folder, root):
    return os.path.normcase(folder) == os.path.normcase(root) or _same_file(folder, root)


def _write_undo(undo_file, record):
    with undo_file.open("x", encoding="utf-8") as output:
        json.dump(record, output, indent=1)
        output.flush()
        os.fsync(output.fileno())


def _connect(database, apply):
    uri = Path(database).resolve(strict=True).as_uri()
    conn = sqlite3.connect(f"{uri}?mode={'rw' if apply else 'ro'}", uri=True, isolation_level=None)
    conn.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
    return conn


def rename(database, apply=False, username=None, path_root=None, config=None, profile=None, sample=20):
    """Preview, or with `apply` carry out, the renames for the creator a
    user_data.db holds the rows of (see the module's docstring)."""
    if apply and postgres.enabled():
        raise ValueError(POSTGRES_REFUSED)
    database = Path(database).resolve(strict=True)
    with closing(_connect(database, apply)) as conn:
        with scraper_settings(config, profile, _site(conn)) as settings:
            result, to_do, roots = plan(conn, settings, username, path_root)
        result["database"] = str(database)
        result["applied"] = apply
        result["renames"] = [{"from": old, "to": new} for _what, old, new, _rows in to_do
                             ][: sample or None]
        if not apply or not to_do:
            conn.rollback()
            return result
        undo_file = database.with_name(f"{database.name}.rename-undo-{uuid.uuid4().hex}.json")
        record = {
            "version": UNDO_VERSION, "tool": TOOL, "database": str(database),
            "files": [{"from": old, "to": new, "rows": [list(change[:5]) for change in changes]}
                      for _what, old, new, changes in to_do],
        }
        _write_undo(undo_file, record)
        moved = []
        try:
            for what, old, new, changes in to_do:
                if what == "rename":
                    # listed before it is made: a stop (Ctrl+C) in or just
                    # after it still finds it to put back
                    moved.append((old, new))
                    try:
                        rename_file(old, new)
                    except OSError as error:
                        # another disk, a folder that can't be written to
                        moved.pop()
                        result["left"].append({"file": old, "why": f"it could not be renamed ({error.strerror or error})"})
                        result["to_rename"] -= 1
                        continue
                    result["renamed"] += 1
                for rowid, directory, filename, new_dir, new_name, _size in changes:
                    changed = conn.execute(
                        "UPDATE medias SET directory = ?, filename = ? WHERE rowid = ? AND directory = ? AND filename = ?",
                        (new_dir, new_name, rowid, directory, filename),
                    ).rowcount
                    if changed != 1:
                        # the file is locked: only a row that is gone, or
                        # changed by hand while this ran, gets here
                        raise ValueError(mover.MEANWHILE)
                    result["rows_changed"] += 1
        except BaseException as error:
            _apply_rolled_back(conn, moved, undo_file, error)
            raise
        try:
            conn.commit()
        except BaseException as error:
            if _still_open(conn):
                # the commit didn't happen (a reader held the file, say):
                # nothing was saved, so the files get their old names back
                _apply_rolled_back(conn, moved, undo_file, error)
                raise
            raise _unconfirmed(
                error,
                f"The undo file is kept: {undo_file}. Run this with --undo and that"
                " file, without --apply, to see what it would put back.",
                saved_to="the database file",
            ) from error
    result["undo_file"] = str(undo_file)
    if not result["rows_changed"]:
        # nothing was renamed: there is nothing to undo
        with contextlib.suppress(OSError):
            undo_file.unlink()
            result["undo_file"] = None
    result["folders_removed"] = _remove_emptied([old for old, _new in moved], *roots)
    return result


def _still_open(conn):
    """True when a commit that failed left its transaction open: nothing
    was saved, and rolling back is safe. False when it isn't known."""
    try:
        return conn.in_transaction
    except sqlite3.Error:
        return False


def _roll_back(conn):
    # a failed rollback still saves nothing: closing the connection drops it
    with contextlib.suppress(sqlite3.Error):
        conn.rollback()


def _apply_rolled_back(conn, moved, undo_file, error):
    """--apply stopped before its rows were saved: give the renamed files
    their old names back. The undo file is removed only when every file is
    seen back at its old name (no row was saved); otherwise, or when a
    second stop lands while they are put back, it is kept, and an undo with
    it changes only what is still as this run left it."""
    _roll_back(conn)
    left = _move_back(moved)
    if left:
        print(f"Files that could not be given their old names back: {len(left)}.", file=sys.stderr)
    elif all(os.path.lexists(old) for old, _new in moved):
        try:
            undo_file.unlink()
        except OSError:
            pass
        else:
            return
    print(f"The undo file is kept: {undo_file}", file=sys.stderr)


def _undo_rolled_back(conn, moved):
    """An undo stopped before its rows were saved: the rows keep the new
    names, so the files renamed back get their new names again."""
    _roll_back(conn)
    left = _move_back(moved)
    if left:
        print(
            "Files left at their old names while their rows keep the new ones: "
            + ", ".join(left),
            file=sys.stderr,
        )


def _move_back(moved):
    """Give renamed files their old names back; what can't be is returned.
    A rename stopped before it was made has nothing at its new place; one
    stopped after its link has the file at both, and rename_file then only
    removes the new name."""
    left = []
    for old, new in reversed(moved):
        if not os.path.lexists(new):
            continue
        try:
            rename_file(new, old)
        except OSError:
            left.append(new)
    return left


def _read_undo(undo_file):
    record = json.loads(Path(undo_file).read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("tool") != TOOL:
        raise ValueError("This isn't an undo file written by rename_to_format")
    if record.get("version") != UNDO_VERSION:
        raise ValueError("Undo file was written by a version of this command that this one doesn't know")
    files = record.get("files")
    if not isinstance(files, list) or any(
        not isinstance(f, dict) or not isinstance(f.get("from"), str) or not isinstance(f.get("to"), str)
        or not isinstance(f.get("rows"), list) or any(not isinstance(r, list) or len(r) != 5 for r in f["rows"])
        for f in files
    ):
        raise ValueError("Invalid files in the undo file")
    return record


def undo(undo_file, apply=False):
    """Put back what a --apply changed, as far as it is still as that left
    it. A file at its new place, with nothing at its old one, gets its old
    name back; then the rows that still record its new name get the old
    one. A file that is at neither place, or at both, is listed and its
    rows are left."""
    if apply and postgres.enabled():
        raise ValueError(POSTGRES_REFUSED)
    record = _read_undo(undo_file)
    database = Path(record["database"]).resolve(strict=True)
    result = {"applied": apply, "database": str(database), "files_to_rename_back": 0,
              "rows_to_restore": 0, "renamed_back": 0, "rows_restored": 0, "left": []}
    condition = "rowid = ? AND directory = ? AND filename = ?"
    with closing(_connect(database, apply)) as conn:
        # (new, old): what the rows' rollback would leave misnamed
        moved = []
        try:
            for entry in record["files"]:
                old, new = entry["from"], entry["to"]
                at_old, at_new = _where(old, new)
                # at both as one file: an undo that stopped after its link
                if at_new and (not at_old or _same_file(old, new)):
                    result["files_to_rename_back"] += 1
                    if apply:
                        # listed before it is made, as in rename()
                        moved.append((new, old))
                        try:
                            rename_file(new, old)
                        except OSError as error:
                            moved.pop()
                            result["left"].append({"file": new, "why": f"it could not be renamed ({error.strerror or error})"})
                            continue
                        result["renamed_back"] += 1
                elif at_new or not at_old:
                    why = "at its old place and its new one" if at_new else NOT_FOUND
                    result["left"].append({"file": new, "why": why})
                    continue
                for rowid, directory, filename, new_dir, new_name in entry["rows"]:
                    found = conn.execute(
                        f"SELECT COUNT(*) FROM medias WHERE {condition}", (rowid, new_dir, new_name)
                    ).fetchone()[0]
                    result["rows_to_restore"] += found
                    if apply and found:
                        conn.execute(
                            f"UPDATE medias SET directory = ?, filename = ? WHERE {condition}",
                            (directory, filename, rowid, new_dir, new_name),
                        )
                        result["rows_restored"] += 1
        except BaseException:
            _undo_rolled_back(conn, moved)
            raise
        try:
            conn.commit()
        except BaseException:
            if _still_open(conn):
                # the commit didn't happen (a reader held the file, say)
                _undo_rolled_back(conn, moved)
            else:
                print(
                    "The undo was stopped while its rows were being saved, so it"
                    f" isn't known whether they were. The undo file is kept: {undo_file}",
                    file=sys.stderr,
                )
            raise
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ofscraper rename_to_format", description=__doc__.split("\n\n")[0])
    parser.add_argument("database", type=Path, nargs="?", help="One creator's user_data.db")
    parser.add_argument("--apply", action="store_true", help="Rename the files and change the rows; writes an undo file first. Without it, only report")
    parser.add_argument("--username", metavar="NAME", help="The recorded name to build {model_username} from (default: the name seen last)")
    parser.add_argument("--config", "-cg", metavar="PATH", help="The scraper's config.json, or its folder, as the scraper's --config (default: the scraper's)")
    parser.add_argument("--profile", "-r", metavar="NAME", help="The scraper profile, for {profile} (default: config.json's main_profile)")
    parser.add_argument("--path-root", type=Path, help="Original working directory for relative recorded paths")
    parser.add_argument("--sample", type=int, default=20, metavar="N", help="List up to N of the renames (default 20; 0 lists all)")
    parser.add_argument("--undo", metavar="FILE", help="Preview putting back what an --apply changed, from its undo file; with --apply, put it back")
    args = parser.parse_args(argv)

    if args.undo is not None:
        if args.database or args.username or args.config or args.profile or args.path_root:
            parser.error("--undo takes the database from the undo file; give only --apply with it")
    elif not args.database:
        parser.error("the following arguments are required: database")
    elif not args.apply and os.environ.get(postgres.URL_KEY, "").strip():
        # with --apply, rename() refuses instead
        print(f"warning: {FILES_NOTICE}", file=sys.stderr)

    # the placeholder code's warnings are for a download's log
    logging.getLogger("shared").addHandler(logging.NullHandler())
    try:
        if args.undo is not None:
            result = undo(args.undo, apply=args.apply)
        else:
            result = rename(args.database, apply=args.apply, username=args.username, path_root=args.path_root,
                            config=args.config, profile=args.profile, sample=args.sample)
    except KeyboardInterrupt:
        parser.exit(130, "Rename stopped.\n")
    except postgres.Unconfirmed as error:
        parser.exit(130 if error.interrupted else 1, f"Rename failed: {error}\n")
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(1, f"Rename failed: {error}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
