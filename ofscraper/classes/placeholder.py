import datetime
import logging
import os
import pathlib
import platform
import re
import string
import arrow

import ofscraper.sites as sites
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.config.data as data
import ofscraper.utils.config.file as config_file
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.me as me
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.paths.paths as paths
import ofscraper.utils.profiles.data as profile_data
import ofscraper.utils.settings as settings
import ofscraper.utils.dry_run as dry_run
from ofscraper.utils.string import parse_safe
from ofscraper.utils.config.naming_check import (
    LIVE_TIME_FIELDS, LIVE_TYPE_KEYS, name_safe, type_name, used_type_options,
)
import ofscraper.managers.manager as manager
from ofscraper.scripts.naming_script import naming_script

log = logging.getLogger("shared")


def post_date(date, fallback, name, ele):
    """The date behind {date}, {year}, {month} and {day}: the post's date,
    else ``fallback`` (the media's own date), else 0 (1970), as the database
    readers store a missing date.

    Names are built several times per file (temporary folder, folder, file
    name), so the warning is logged once per item, remembered on ``ele``."""
    if not date:
        date = fallback or 0
        if not getattr(ele, "_undated_name_warned", False):
            ele._undated_name_warned = True
            log.warning(
                f"{name} has no date, {'using its media date' if date else 'using 1970-01-01'}"
                " for {date} in its file and folder names"
            )
    return arrow.get(date)


# can't be in a folder or file name on Windows; a slash would add a folder
_NOT_IN_A_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def path_safe_label(label):
    """The {label} value: the label's name without characters a file name
    can't hold. Names arrive decoded ("Q&A <3", not "Q&amp;A &lt;3"), so
    ``<`` and ``>`` would otherwise stop the folder being made on Windows.
    Spaces and dashes are kept, so existing label folders keep their names."""
    return _NOT_IN_A_NAME.sub("", str(label)).strip() or "None"


def site_save_location():
    """Save location; Fansly runs use ``<save location>/Fansly``.

    OnlyFans gets the configured value unchanged (same type, no Path round trip).
    """
    location = common_paths.get_save_location()
    if sites.is_fansly():
        return str(pathlib.Path(location, sites.site_name()))
    return location


# Placeholders whose value differs between OnlyFans and Fansly. {model_id} counts:
# Fansly ids are 18-digit snowflakes, OnlyFans ids are far shorter.
_SITE_SPECIFIC_FIELDS = {
    "save_location", "savelocation", "root", "site_name", "sitename",
    "model_id", "modelid",
}


def _template_fields(*formats):
    return {
        name.split(".")[0].split("[")[0]
        for fmt in formats
        for _, name, _, _ in string.Formatter().parse(fmt or "")
        if name
    }


def _is_site_specific(fmt):
    """True when ``fmt`` resolves to a different path for each site."""
    return bool(_template_fields(fmt) & _SITE_SPECIFIC_FIELDS)


def _names_site(fmt):
    """True when ``fmt`` uses {site_name} (or {sitename})."""
    return bool(_template_fields(fmt) & {"site_name", "sitename"})


def default_media_root(save_location=None, dir_format=None, file_format=None, *, site_name=None):
    """The folder ``dir_format`` is placed under: ``save_location`` (the
    file_options one when not given). Fansly gets a ``Fansly`` folder in it,
    unless ``dir_format`` or ``file_format`` already names the site with
    {site_name}: then each site's folder comes from the template, and Fansly
    files don't get a second ``Fansly`` folder. Only the media folder: the
    database path and the {save_location} and {root} values keep the
    ``Fansly`` folder either way."""
    base = save_location or common_paths.get_save_location()
    dir_fmt = dir_format if dir_format is not None else data.get_dirformat()
    file_fmt = file_format if file_format is not None else data.get_fileformat()
    site = site_name or sites.site_name()
    if site.lower() == sites.FANSLY and not (_names_site(dir_fmt) or _names_site(file_fmt)):
        return pathlib.Path(base, site)
    return pathlib.Path(base)


def _type_settings(type_keys):
    """The type_options values for these types (names matched as
    naming_check.type_name compares them); when two types set a value, the
    first type's wins."""
    by_name = {type_name(name): section for name, section in data.get_type_options().items()}
    found = {}
    for key in type_keys:
        for field, value in by_name.get(type_name(key), {}).items():
            if isinstance(value, str) and value.strip():
                found.setdefault(field, value)
    return found


def type_save_location(type_keys):
    """The save_location a type_options entry sets for these types, or None"""
    return _type_settings(type_keys).get("save_location")


def media_templates(type_keys, *, save_location=None, dir_format=None, file_format=None, site_name=None):
    """(root, dir_format, file_format) for these types: type_options first,
    then the values given, then file_options."""
    found = _type_settings(type_keys)
    dir_fmt = found.get("dir_format") or dir_format or data.get_dirformat()
    file_fmt = found.get("file_format") or file_format or data.get_fileformat()
    root = default_media_root(
        found.get("save_location") or save_location, dir_fmt, file_fmt, site_name=site_name
    )
    return root, dir_fmt, file_fmt


def media_type_keys(ele):
    """The types a media file's type_options entry is looked up by: its
    area, its area as responsetype names it, then its media type"""
    return (ele.responsetype, ele.modified_responsetype, ele.mediatype)


def media_roots():
    """Every folder downloads are saved under: the save location's and each
    type_options entry's but the livestream one."""
    roots = [default_media_root()]
    roots.extend(
        media_templates((name,))[0] for name in used_type_options()
        if type_name(name) not in LIVE_TYPE_KEYS
    )
    return list(dict.fromkeys(roots))


def _base_path_variables(save_location, site_name, *, include_account=True):
    """Common path context; live templates fetch account identity only when used."""
    my_username, my_id = "", ""
    if include_account:
        _, my_username = me.parse_user()
        my_id = "anon" if settings.get_settings().anon else me.get_id()
    return {
        "config_path": common_paths.get_config_home(),
        "profile": profile_data.get_active_profile(),
        "site_name": site_name,
        "save_location": save_location,
        "root": pathlib.Path(save_location),
        "my_id": my_id,
        "my_username": my_username,
    }


def _add_aliases(variables):
    variables.update({key.replace("_", ""): value
                      for key, value in list(variables.items()) if "_" in key})


DEFAULT_LIVE_DIR_FORMAT = "{sitename}/{model_username}/Livestreams"
DEFAULT_LIVE_FILE_FORMAT = "{model_username}_{date}_live"


def _relative_folder(folder):
    folder = pathlib.Path(folder)
    if folder.anchor:
        # A drive-relative path needs a root before normalizing its parent components.
        if not folder.root:
            folder = pathlib.Path(f"{folder.drive}/", *folder.parts[1:])
        folder = pathlib.Path(os.path.normpath(folder))
        return pathlib.Path(*folder.parts[1:])
    return folder


def _template_folder(root, folder):
    return pathlib.Path(os.path.normpath(root / _relative_folder(folder)))


def live_recording_path(
    save_location,
    username: str,
    started_at: datetime.datetime,
    *,
    site_name: str,
    ext: str,
    model_id=None,
    reserve_suffix="",
) -> pathlib.Path:
    """A livestream's file: type_options.livestreams, then live_options, then
    ``{sitename}/{model_username}/Livestreams/{model_username}_{date}_live``
    under the save location. A template that can't be filled in (an unknown
    placeholder) falls back to the default names, in the same save
    location, with a warning, so the stream is still recorded."""
    context = dict(username=username, started_at=started_at, site_name=site_name,
                   model_id=model_id, ext=ext)
    try:
        path = _live_path(*live_templates(save_location, site_name), **context)
    except (KeyError, AttributeError, IndexError, TypeError, ValueError) as E:
        log.warning(
            f"The livestream folder or file name template can't be filled in ({E!r}),"
            f" so {username}'s recording uses the default name"
        )
        # the default names, but still the save location the settings choose
        default = media_templates(
            (), save_location=live_save_location(save_location), dir_format=DEFAULT_LIVE_DIR_FORMAT,
            file_format=DEFAULT_LIVE_FILE_FORMAT, site_name=site_name,
        )
        path = _live_path(*default, **context)
    if not reserve_suffix:
        return final_path(path)
    base = fit_with_suffix(path.with_suffix(""), reserve_suffix, started_at)
    return base.with_name(base.name + path.suffix)


def fit_with_suffix(base, suffix, started_at):
    """``base`` (a recording's name without its extension) shortened so that
    ``base`` + ``suffix`` fits. A cut keeps the stream's start time and what
    follows it ("_live"), so two recordings' names stay apart."""
    base = pathlib.Path(base)
    stamp = re.search(r"_?\d{8}_\d{6}$", base.name)
    keep = (stamp.group() if stamp else "") + suffix
    candidate = base.with_name(base.name + suffix)
    fitted = final_path(candidate, keep_suffix=keep)
    if started_at is not None and fitted.name != candidate.name:
        timestamp = started_at.strftime("%Y%m%d_%H%M%S")
        prefix, matched, tail = base.name.rpartition(timestamp)
        if not matched:
            prefix, timestamp, tail = base.name, f"_{timestamp}", ""
        keep = timestamp + tail + suffix
        if not fitted.name.endswith(keep):
            try:
                fitted = final_path(base.with_name(prefix + keep), keep_suffix=keep)
            except ValueError:
                if not tail:
                    raise
                keep = timestamp + suffix
                fitted = final_path(base.with_name(prefix + keep), keep_suffix=keep)
    return fitted.with_name(fitted.name.removesuffix(suffix))


def live_save_location(save_location=None):
    """Where livestreams are saved: type_options.livestreams, then
    live_options, then ``save_location``"""
    return (
        type_save_location(LIVE_TYPE_KEYS)
        or data.get_live_save_location()
        or save_location
    )


def live_templates(save_location=None, site_name=None):
    """(root, dir_format, file_format) livestreams are saved with"""
    return media_templates(
        LIVE_TYPE_KEYS,
        save_location=live_save_location(save_location),
        dir_format=data.get_live_dirformat() or DEFAULT_LIVE_DIR_FORMAT,
        file_format=data.get_live_fileformat() or DEFAULT_LIVE_FILE_FORMAT,
        site_name=site_name,
    )


def live_names_apart(dir_fmt, file_fmt):
    """True when the names hold the start time, so two of one creator's
    recordings don't get the same file"""
    return bool(_template_fields(dir_fmt, file_fmt) & LIVE_TIME_FIELDS)


def _live_path(root, dir_fmt, file_fmt, *, username, started_at, site_name, model_id, ext):
    fields = _template_fields(dir_fmt, file_fmt)
    variables = _base_path_variables(
        str(root), site_name,
        include_account=bool(fields & {"my_id", "myid", "my_username", "myusername"}),
    )
    stamp = started_at.strftime("%Y%m%d_%H%M%S")
    variables.update({
        "user_name": username,
        "username": username,
        "model_username": username,
        "model_id": model_id if model_id is not None else "",
        "first_letter": username[0].capitalize() if username else "U",
        "response_type": "Livestreams",
        "media_type": "Videos",
        "date": stamp,
        "timestamp": stamp,
        "year": started_at.strftime("%Y"),
        "month": started_at.strftime("%m"),
        "day": started_at.strftime("%d"),
        "ext": ext,
        "config": config_file.open_config(),
        "args": settings.get_args(),
    })
    _add_aliases(variables)
    folder = _relative_folder(_safe_format(dir_fmt, variables))
    paths.validate_directory_parts(folder.parts)
    stem = _safe_format(file_fmt, variables)
    if stem.lower().endswith(f".{ext.lower()}"):
        stem = stem[: -(len(ext) + 1)]
    if not stem or pathlib.Path(stem).name != stem or stem in (".", ".."):
        log.warning("The livestream file name must be a single path component, "
                    f"so {username}'s recording uses the default name")
        file_fmt = DEFAULT_LIVE_FILE_FORMAT
        stem = _safe_format(file_fmt, dict(variables, model_username=name_safe(username)))
    if not live_names_apart(dir_fmt, file_fmt):
        stem = f"{stem}_{stamp}"
    return pathlib.Path(os.path.normpath(root / folder), f"{stem}.{ext}")


def final_path(path, *, keep_suffix=""):
    """The path a file is saved at: shortened to what the system allows,
    unless --original or truncation_default: false turns that off."""
    if getattr(settings.get_settings(), "trunicate", True):
        if keep_suffix:
            return paths.truncate(pathlib.Path(path), keep_suffix=keep_suffix)
        return paths.truncate(pathlib.Path(path))
    return pathlib.Path(os.path.normpath(path))


class basePlaceholder:
    def __init__(self) -> None:
        self._ele = None

    def create_variables_base(self):
        # Metadata keeps the site root even when the media template names the site.
        self._variables = _base_path_variables(site_save_location(), sites.site_name())

    def async_wrapper(f):
        async def inner(*args, **kwargs):
            args[0]._variables = {}
            args[0].create_variables_base()
            return await f(args[0], *args[1:], **kwargs)

        return inner

    def wrapper(f):
        def inner(*args, **kwargs):
            args[0]._variables = {}
            args[0].create_variables_base()
            return f(args[0], *args[1:], **kwargs)

        return inner

    def add_no_underline(self):
        _add_aliases(self._variables)

    def templates(self):
        """(root, dir_format, file_format) for this item, worked out once"""
        if getattr(self, "_templates", None) is None:
            self._templates = media_templates(self.type_keys())
        return self._templates


class tempFilePlaceholder(basePlaceholder):
    def __init__(self, ele, tempname) -> None:
        super().__init__()
        self._ele = ele
        self._placeholder = Placeholders(self._ele, "mp4")
        self._tempname = tempname

    async def init(self):
        dir = await self.gettempDir(self._ele)
        file = self._tempname
        # remove for now
        # if env.getattr("ALLOW_DUPE_MEDIA"):
        #     file=f"{''.join(random.choice(string.ascii_letters + string.digits) for _ in range(6))}{file}"
        script_name = await naming_script(dir, file, self._ele, self._placeholder.templates()[1:])
        self._tempfilepath = final_path(script_name or pathlib.Path(dir, file))
        return self

    @basePlaceholder.async_wrapper
    async def gettempDir(self, ele, create=True):
        self._tempdir = await self._placeholder.getmediadir(
            root=(data.get_TempDir()),
            create=create,
        )
        self._tempdir.mkdir(parents=True, exist_ok=True)
        return self._tempdir

    @property
    def tempfilepath(self):
        return pathlib.Path(self._tempfilepath)

    @property
    def tempfilename(self):
        return pathlib.Path(self._tempfilepath).name


class databasePlaceholder(basePlaceholder):
    def __init__(self, create=True) -> None:
        """create=False works out the database path without making the
        creator's folder, for a read-only read (#373)."""
        super().__init__()
        self._create = create

    @basePlaceholder.wrapper
    def databasePathHelper(self, model_id, model_username):
        self._variables.update({"username": model_username})
        self._variables.update({"model_username": model_username})
        self._variables.update({"first_letter": model_username[0].capitalize()})
        self._variables.update({"model_id": model_id})
        self.add_no_underline()
        globals().update(self._variables)
        log.trace(
            f"modelid:{model_id}  database placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        metadata_format = data.get_metadata()
        formatStr = metadata_format.format(**self._variables)
        if sites.is_fansly() and not _is_site_specific(metadata_format):
            # e.g. {configpath}/{profile}/.data/{model_username} resolves to the
            # same folder on both sites; keep Fansly rows out of the OnlyFans db
            formatStr = pathlib.Path(formatStr, sites.site_name())
        data_path = pathlib.Path(formatStr, "user_data.db")
        data_path = pathlib.Path(os.path.normpath(data_path))
        if dry_run.active():
            # a dry run reads and writes a throwaway copy (utils/dry_run.py)
            data_path = dry_run.redirect(data_path)
        self._metadata = data_path
        # a read-only read makes no folder (#373)
        if self._create:
            self._metadata.parent.mkdir(parents=True, exist_ok=True)
        log.trace(f"final database path {data_path}")
        return pathlib.Path(data_path)

    def databasePathCopyHelper(self, model_id, model_username):
        counter = (
            cache.get(f"{model_username}_{model_id}_dbcounter", default=0) % 5
        ) + 1
        cache.set(f"{model_username}_{model_id}_dbcounter", counter)

        return pathlib.Path(
            re.sub(
                "user_data.db",
                f"/backup/user_data_copy_{counter}.db",
                str(self.databasePathHelper(model_id, model_username)),
            )
        )

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, input):
        self._metadata = input


# names Windows keeps for devices, with or without an extension ("con.txt")
_WINDOWS_DEVICE = re.compile(r"(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?=\s*(\.|$))")


def _on_windows():
    return platform.system() == "Windows"


def _safe_parts(path, literal=None):
    """path with no folder or file name that is only dots ("." or ".." would
    be this folder or the one above; Windows drops trailing spaces and dots,
    so ". " is "." and " ." nothing) or, on Windows, a device name ("CON"
    gets "CON_"): a caption or a name can be either. literal marks each character the template itself wrote: a
    name made only of those (dir_format ".", to save in save_location) is
    kept."""
    path = str(path)
    literal = literal or [False] * len(path)
    out, start = [], 0
    for part in re.split(r"([/\\])", path):
        own = all(literal[start : start + len(part)])
        start += len(part)
        if len(out) % 2:
            pass
        elif re.fullmatch(r"\s*\.[.\s]*", part) and not own:
            part = "_"
        elif _on_windows():
            # only Windows has device names: elsewhere "aux" is a name
            part = _WINDOWS_DEVICE.sub(r"\1_", part)
        out.append(part)
    return "".join(out)


def _safe_format(template, variables):
    """template.format(**variables) through _safe_parts, which keeps a "." the
    template writes but not one a value (a caption) makes"""
    text, literal = "", []
    for lit, field, spec, conv in string.Formatter().parse(template):
        text += lit
        literal += [True] * len(lit)
        if field is None:
            continue
        value = ("{" + field + (f"!{conv}" if conv else "") + f":{spec}}}").format(
            **variables
        )
        text += value
        literal += [False] * len(value)
    return _safe_parts(text, literal)


def _safe_name(out, template, variables):
    """out through _safe_parts. When out is the template filled in, a "." the
    template writes is kept, as in _safe_format. Otherwise the folders the
    template writes before any placeholder ("./" in "./{text}.{ext}") are
    kept when out starts with them."""
    try:
        same = out == template.format(**variables)
    except Exception:
        same = False
    if same:
        return _safe_format(template, variables)
    try:
        first = next(iter(string.Formatter().parse(template)), ("",))[0] or ""
    except ValueError:
        first = ""
    prefix = first[: max(first.rfind("/"), first.rfind("\\")) + 1]
    if prefix and out.startswith(prefix):
        return _safe_parts(out, [True] * len(prefix) + [False] * (len(out) - len(prefix)))
    return _safe_parts(out)


class _ContentPlaceholder(basePlaceholder):
    _skip_mediadir = False

    def __init__(self, ele, ext) -> None:
        super().__init__()
        self._filename = None
        self._mediadir = None
        self._metadata = None
        self._filepath = None
        self._ele = ele
        self._ext = ext

    def add_price_variables(self, username):
        modelObj = manager.Manager.current_model_manager.get_model(username)
        placeholder_val = of_env.getattr("MODEL_PRICE_PLACEHOLDER")

        def _label(attr):
            if not modelObj:
                return placeholder_val
            return "Free" if getattr(modelObj, attr) == 0 else "Paid"

        self._variables.update(
            {
                "current_price": _label("final_current_price"),
                "regular_price": _label("final_regular_price"),
                "promo_price": _label("final_promo_price"),
                "renewal_price": _label("final_renewal_price"),
            }
        )

    async def add_common_variables(self, ele, username, model_id):
        await self.add_main_variables(ele, username, model_id)
        self.add_price_variables(username)
        self.add_no_underline()

    def _add_shared_variables(
        self,
        ele,
        username,
        model_id,
        *,
        post_id,
        media_id,
        posted,
        media_type,
        download_type,
    ):
        self._variables.update(
            {
                "user_name": username,
                "model_id": model_id,
                "post_id": post_id,
                "media_id": media_id,
                "first_letter": username[0].capitalize(),
                "media_type": media_type,
                "value": ele.value.capitalize(),
                "date": posted.format(data.get_date()),
                "year": posted.format("YYYY"),
                "month": posted.format("MM"),
                "day": posted.format("DD"),
                "model_username": username,
                "response_type": ele.modified_responsetype,
                "label": path_safe_label(ele.label_string),
                "download_type": download_type,
                "modelObj": manager.Manager.current_model_manager.get_model(username),
                "config": config_file.open_config(),
                "args": settings.get_args(),
            }
        )

    @basePlaceholder.async_wrapper
    async def getmediadir(self, root=None, create=True):
        if self._skip_mediadir and of_env.getattr("SKIP_MEDIADIR_RETRIVAL"):
            return None
        ele = self._ele
        username = ele.username
        model_id = ele.model_id
        default_root, dir_fmt, _ = self.templates()
        root = pathlib.Path(root) if root else default_root
        await self.add_common_variables(ele, username, model_id)
        # the date setting can hold ":" or "*", which a folder name can't on
        # Windows; a date fills one folder, so its "/" adds none
        if "date" in self._variables:
            self._variables["date"] = name_safe(self._variables["date"])
        globals().update(self._variables)
        log.trace(
            f"modelid:{model_id}  mediadir placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        final_path = _template_folder(root, _safe_format(dir_fmt, self._variables))
        log.trace(f"final mediadir path {final_path}")
        self._mediadir = final_path
        self._mediadir.mkdir(parents=True, exist_ok=True) if create else None
        return final_path

    @property
    def filepath(self):
        return pathlib.Path(self._filepath)

    @property
    def filename(self):
        return pathlib.Path(self._filepath).name

    @property
    def filedir(self):
        return pathlib.Path(self._filepath).parent

    @property
    def trunicated_filename(self):
        return pathlib.Path(self.trunicated_filepath).name

    @property
    def trunicated_filepath(self):
        if getattr(settings.get_settings(), "trunicate", True):
            return pathlib.Path(paths.truncate(self._filepath))
        return self._filepath


class Placeholders(_ContentPlaceholder):
    _skip_mediadir = True

    def type_keys(self):
        return media_type_keys(self._ele)

    async def init(self, create=True):
        dir = await self.getmediadir(create=create)
        file = await self.createfilename()
        script_name = await naming_script(dir, file, self._ele, self.templates()[1:])
        if not script_name:
            file = self._fit_text(dir, file)
        self._filepath = final_path(script_name or pathlib.Path(dir, file))
        return self

    def _fit_text(self, dir, file):
        """A name too long for the path, with {text} made just short enough
        to fit, so the end of the name ({filename}, {media_id} and the rest
        after the caption) isn't cut instead (#741). The name unchanged when
        it fits, or when it doesn't fit even with no caption. Left alone, as
        the rest of the path is, when --original or truncation_default: false
        turns shortening off."""

        def fits(name):
            if name is None:
                return False
            try:
                return paths.truncate(pathlib.Path(dir, name)).name == name
            except ValueError:
                # not even the start of the name fits
                return False

        text = self._variables.get("text")
        if (
            not getattr(settings.get_settings(), "trunicate", True)
            or not text
            or self._ele.responsetype.capitalize() == "Profile"
            or fits(file)
            or not fits(self._name_with_text(""))
        ):
            return file
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if fits(self._name_with_text(text[:mid])):
                low = mid
            else:
                high = mid - 1
        return self._name_with_text(text[:low])

    def _name_with_text(self, text):
        """The name with this caption, or None when nothing is left before
        the extension: a nameless ".jpg" is no name, nor is the "_1.jpg" a
        count makes of it (the count repeats in every post), but "_70.jpg"
        from "{text}_{media_id}" is."""
        file_fmt = self.templates()[2]
        out = file_fmt.format(**{**self._variables, "text": text.rstrip()})
        if not re.sub(r"\.[a-z0-9]{1,10}$", "", out, flags=re.IGNORECASE).strip():
            return None
        return self._addcount(self._ele, out, file_fmt)

    async def add_main_variables(self, ele, username, model_id):
        posted = post_date(
            ele.postdate, ele.date, f"Post {ele.post_id} (media {ele.id})", ele
        )
        self._add_shared_variables(
            ele,
            username,
            model_id,
            post_id=ele.post_id,
            media_id=ele.id,
            posted=posted,
            media_type=ele.mediatype.capitalize(),
            download_type=ele.downloadtype,
        )
        self._variables.update(
            {
                "quality": await ele.selected_quality_placeholder,
                "file_name": await ele.final_filename,
                "original_filename": ele.filename,
                "only_file_name": ele.no_quality_final_filename,
                "only_filename": ele.no_quality_final_filename,
                "text": ele.file_text,
            }
        )

    @basePlaceholder.async_wrapper
    async def createfilename(self):
        if of_env.getattr("SKIP_FILENAME_RETRIVAL"):
            return None
        ele = self._ele
        ext = self._ext
        username = ele.username
        model_id = ele.model_id
        file_fmt = self.templates()[2]
        self._variables.update({"ext": ext})
        await self.add_common_variables(ele, username, model_id)
        # the date setting can hold "/", which a folder can use but a file
        # name can't
        self._variables.update({"date": name_safe(self._variables["date"])})
        globals().update(self._variables)
        log.trace(
            f"model_id:{model_id}  filename placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        out = None
        if ele.responsetype.capitalize() == "Profile":
            out = _safe_parts(f"{await ele.final_filename}.{ext}")
        else:
            out = _safe_format(file_fmt, self._variables)
        out = self._addcount(ele, out, file_fmt)
        log.debug(f"final filename path {out}")
        self._filename = out
        return out

    def _addcount(self, ele, out, file_format):
        if not of_env.getattr("FILE_COUNT_PLACEHOLDER"):
            return out
        elif not self._needs_count(ele, file_format):
            return out
        out = re.sub(" $", "", out)
        # insert count, before the extension if there is one: only the last
        # dot, a caption or a date can have dots of its own
        if re.search(r"\.(?:[a-zA-Z0-9]+)$", out):
            out = re.sub(r"(\.[a-zA-Z0-9]+)$", rf"_{ele.count}\1", out)
        else:
            out = f"{out}_{ele.count}"
        return out

    def _needs_count(self, ele, file_format):
        unique = set(
            [
                "filename",
                "file_name",
                "only_file_name",
                "only_filename",
                "onlyfilename",
                "original_filename",
                "originalfilename",
                "media_id",
                "mediaid",
            ]
        )
        file_format = parse_safe(file_format)
        # return early if pass
        if len((unique & file_format)) > 0:
            return False
        elif len(ele._post.post_media) > 1 or ele.responsetype.lower() in [
            "stories",
            "highlights",
        ]:
            return True
        return False

    @property
    def trunicated_filedir(self):
        return pathlib.Path(self.trunicated_filepath).parent

    @property
    def size(self):
        if not self.trunicated_filepath:
            return
        elif not self.trunicated_filepath.exists():
            return
        else:
            return self.trunicated_filepath.stat().st_size


# the placeholders that are the caption for a text file, in every spelling
_CAPTION_NAMES = (
    "file_name", "filename",
    "only_file_name", "only_filename", "onlyfilename",
    "original_filename", "originalfilename",
)
# stands where a left-out placeholder was until the name is put together
_LEFT_OUT = "\0"
# mark where each placeholder's value starts and ends, so that only the
# separators written in file_format are taken, never a value's own dots
_START, _END = "\x01", "\x02"


_SEP = r"[ _.-]*"


class _MarkedFormatter(string.Formatter):
    def format_field(self, value, format_spec):
        out = super().format_field(value, format_spec)
        return out if out in ("", _LEFT_OUT) else f"{_START}{out}{_END}"


def _without_left_out(file_format, variables, fill):
    """file_format filled in without a left-out placeholder and the separators
    beside it. Brackets around it go too. Between two parts, one separator is
    kept: the one after it ("{date} {filename} {text}" gives "date text"), or
    the one before it when nothing follows it. A folder named by it alone is
    left out with its slash ("{filename}/{text}" gives "text"). When the file
    name would be left with nothing before its extension, fill is used there
    ("{text}/{filename}.{ext}" gives "text/<fill>.ext")."""
    name = _MarkedFormatter().vformat(file_format, (), variables)
    name = re.sub(rf"[(\[]\s*{_LEFT_OUT}\s*[)\]]", _LEFT_OUT, name)
    parts = re.split(r"([/\\])", name)
    kept = []
    for i, part in enumerate(parts):
        if i % 2:  # a slash
            kept.append(part)
            continue
        ext = ""
        if i == len(parts) - 1:
            match = re.search(rf"\.{_START}?[A-Za-z0-9]+{_END}?$", part)
            if match:
                part, ext = part[: match.start()], match.group()
        left_out = _LEFT_OUT in part
        while _LEFT_OUT in part:
            part = re.sub(
                rf"^{_SEP}{_LEFT_OUT}{_SEP}|{_SEP}{_LEFT_OUT}{_SEP}$", "", part
            )
            part = re.sub(
                rf"({_SEP}){_LEFT_OUT}({_SEP})", lambda m: m[2] or m[1], part, count=1
            )
        if left_out and not part and ext:
            part = fill  # not ".txt", a hidden file with no name
        if not part and not ext and kept:
            kept.pop()  # an empty folder name: drop it with its slash
            continue
        kept.append(part + ext)
    name = re.sub(r"^[/\\]", "", "".join(kept))
    return name.replace(_START, "").replace(_END, "")


class Textholders(_ContentPlaceholder):
    def type_keys(self):
        ele = self._ele
        return (ele.responsetype, ele.modified_responsetype, "text")

    async def init(self, create=True):
        dir = await self.getmediadir(create=create)
        file = await self.createfilename()
        script_name = await naming_script(dir, file, self._ele, self.templates()[1:])
        self._filepath = final_path(script_name or pathlib.Path(dir, file))
        return self

    async def add_main_variables(self, ele, username, model_id):
        # a text file is named with the same file_format as media, so it has
        # the media's placeholders too: the post's id for the media id, and
        # Normal, as text is never DRM-protected
        posted = post_date(ele.date, None, f"Post {ele.id}", ele)
        self._add_shared_variables(
            ele,
            username,
            model_id,
            post_id=ele.id,
            media_id=ele.id,
            posted=posted,
            media_type="Text",
            download_type="Normal",
        )
        sanitized_name = ele.text_trunicate(ele.file_sanitized_text)
        self._variables.update(
            {
                "text": sanitized_name,
                "quality": "source",
                "file_name": sanitized_name,
                "original_filename": sanitized_name,
                "only_file_name": sanitized_name,
                "only_filename": sanitized_name,
            }
        )

    @basePlaceholder.async_wrapper
    async def createfilename(self):
        ele = self._ele
        ext = self._ext
        username = ele.username
        model_id = ele.model_id
        file_fmt = self.templates()[2]
        self._variables.update({"ext": ext})
        await self.add_common_variables(ele, username, model_id)
        # the date setting can hold "/", which a folder can use but a file
        # name can't
        self._variables.update({"date": name_safe(self._variables["date"])})
        globals().update(self._variables)
        log.trace(
            f"model_id:{model_id}  filename placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        out = None
        if ele.responsetype.capitalize() == "Profile":
            # file_cleanup has put in space_replacer
            text = ele.file_sanitized_text
            out = f"{text}.{ext}"
        else:
            file_format = file_fmt
            fields = parse_safe(file_format)
            if "text" in fields and any(k in fields for k in _CAPTION_NAMES):
                # a text file's {filename} is its caption, as {text} is: with
                # both in the name the caption would be there twice, so
                # {filename} is left out
                variables = {
                    **self._variables,
                    **dict.fromkeys(_CAPTION_NAMES, _LEFT_OUT),
                }
                out = _without_left_out(
                    file_format, variables, str(self._variables["file_name"])
                )
            else:
                out = file_format.format(**self._variables)
        log.debug(f"final filename path {out}")
        self._filename = _safe_name(out, file_fmt, self._variables)
        return self._filename

    @property
    def filedir(self):
        return pathlib.Path(self.trunicated_filepath).parent
