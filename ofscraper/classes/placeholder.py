import datetime
import logging
import os
import pathlib
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
from ofscraper.utils.string import parse_safe
import ofscraper.managers.manager as manager
from ofscraper.scripts.naming_script import naming_script

log = logging.getLogger("shared")


def date_placeholder(date, fallback, name, ele):
    """The {date} value: the post's date, else ``fallback`` (the media's own
    date), else 0 (1970), as the database readers store a missing date.

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
    return arrow.get(date).format(data.get_date())


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


def _is_site_specific(fmt):
    """True when ``fmt`` resolves to a different path for each site."""
    fields = {
        name.split(".")[0].split("[")[0]
        for _, name, _, _ in string.Formatter().parse(fmt)
        if name
    }
    return bool(fields & _SITE_SPECIFIC_FIELDS)


def _names_site(fmt):
    """True when ``fmt`` uses {site_name} (or {sitename})."""
    return any(
        name and name.split(".")[0].split("[")[0] in {"site_name", "sitename"}
        for _, name, _, _ in string.Formatter().parse(fmt or "")
    )


def default_media_root(save_location=None, dir_format=None, file_format=None):
    """Save location; Fansly profiles save under ``<save location>/Fansly``,
    unless ``dir_format`` or ``file_format`` already names the site with
    {site_name}: then each site's folder comes from the template, and Fansly
    files don't get a second ``Fansly`` folder. Only the media folder: the
    database path and the {save_location} and {root} values keep the
    ``Fansly`` folder either way."""
    base_loc = save_location or common_paths.get_save_location()
    dir_fmt = dir_format if dir_format is not None else data.get_dirformat()
    file_fmt = file_format if file_format is not None else data.get_fileformat()
    if sites.is_fansly():
        if _names_site(dir_fmt) or _names_site(file_fmt):
            return pathlib.Path(base_loc)
        if not save_location:
            return pathlib.Path(site_save_location())
        base_path = pathlib.Path(base_loc)
        if base_path.name.lower() != sites.site_name().lower():
            return base_path / sites.site_name()
        return base_path
    return pathlib.Path(base_loc)


def _resolve_media_templates(type_keys, root=None):
    """Resolve (root_path, dir_format, file_format) with type_options overrides."""
    type_save = data.get_type_option(type_keys, "save_location")
    dir_fmt = data.get_type_option(type_keys, "dir_format") or data.get_dirformat()
    file_fmt = data.get_type_option(type_keys, "file_format") or data.get_fileformat()
    if root is not None:
        resolved_root = pathlib.Path(root)
    else:
        resolved_root = default_media_root(
            save_location=type_save or None,
            dir_format=dir_fmt,
            file_format=file_fmt,
        )
    return resolved_root, dir_fmt, file_fmt


DEFAULT_LIVE_DIR_FORMAT = "{sitename}/{model_username}/Livestreams"
DEFAULT_LIVE_FILE_FORMAT = "{model_username}_{date}_live"


def live_recording_base(
    save_location,
    username: str,
    started_at: datetime.datetime,
    site_name: str | None = None,
    ext: str = "mp4",
) -> pathlib.Path:
    """Resolve the livestream output path without file extension.

    Precedence: ``type_options.livestreams`` -> ``live_options`` ->
    ``save_location`` + built-in ``{sitename}/{model_username}/Livestreams``
    and ``{model_username}_{date}_live`` defaults.
    """
    resolved_site = site_name or sites.site_name()
    override_root = (
        data.get_type_option(("livestreams", "live"), "save_location")
        or data.get_live_save_location()
    )
    root = pathlib.Path(override_root or save_location or common_paths.get_save_location())
    dir_fmt = (
        data.get_type_option(("livestreams", "live"), "dir_format")
        or data.get_live_dirformat()
        or DEFAULT_LIVE_DIR_FORMAT
    )
    file_fmt = (
        data.get_type_option(("livestreams", "live"), "file_format")
        or data.get_live_fileformat()
        or DEFAULT_LIVE_FILE_FORMAT
    )
    is_fansly_site = sites.is_fansly() or resolved_site.lower() == "fansly"
    if is_fansly_site and not (_names_site(dir_fmt) or _names_site(file_fmt)):
        if root.name.lower() != sites.site_name(sites.FANSLY).lower():
            root = root / sites.site_name(sites.FANSLY)
    stamp = started_at.strftime("%Y%m%d_%H%M%S")
    model_obj = None
    try:
        mm = getattr(manager.Manager, "current_model_manager", None)
        model_obj = mm.get_model(username) if mm else None
    except Exception:
        model_obj = None
    model_id = getattr(model_obj, "id", "") if model_obj else ""
    try:
        _, my_username = me.parse_user()
        s = settings.get_settings()
        my_id = "anon" if getattr(s, "anon", False) else me.get_id()
    except Exception:
        my_username, my_id = "", ""
    try:
        active_profile = profile_data.get_active_profile()
        cfg = config_file.open_config()
    except Exception:
        active_profile, cfg = "", {}

    variables = {
        "config_path": common_paths.get_config_home(),
        "profile": active_profile,
        "site_name": resolved_site,
        "save_location": str(root),
        "root": root,
        "my_id": my_id,
        "my_username": my_username,
        "user_name": username,
        "username": username,
        "model_username": username,
        "model_id": model_id,
        "modelObj": model_obj,
        "first_letter": username[0].capitalize() if username else "U",
        "response_type": "Livestreams",
        "media_type": "Videos",
        "date": stamp,
        "timestamp": stamp,
        "ext": ext,
        "config": cfg,
        "args": settings.get_args(),
    }
    for key, val in list(variables.items()):
        if "_" in key:
            variables[key.replace("_", "")] = val

    folder = pathlib.Path(os.path.normpath(str(root / pathlib.Path(dir_fmt.format(**variables)))))
    stem = file_fmt.format(**variables)
    if ext and stem.lower().endswith(f".{ext.lower()}"):
        stem = stem[: -(len(ext) + 1)]
    return folder / stem


def live_recording_path(
    save_location,
    username: str,
    started_at: datetime.datetime,
    site_name: str | None = None,
    ext: str = "webm",
) -> pathlib.Path:
    """Resolve the livestream output file path with extension."""
    base = live_recording_base(
        save_location, username, started_at, site_name=site_name, ext=ext
    )
    return base.with_name(f"{base.name}.{ext}")


class basePlaceholder:
    def __init__(self) -> None:
        self._ele = None

    def create_variables_base(self):
        _, my_username = me.parse_user()
        my_id = "anon" if settings.get_settings().anon else me.get_id()
        # {save_location} and {root} keep the site root (<save location>/Fansly
        # on Fansly runs) even when {site_name} drops it from the media
        # folder, so a metadata path built from them can't reach an OnlyFans
        # user_data.db
        save_location = site_save_location()
        self._variables = {
            "config_path": common_paths.get_config_home(),
            "profile": profile_data.get_active_profile(),
            "site_name": sites.site_name(),
            "save_location": save_location,
            "my_id": my_id,
            "my_username": my_username,
            "root": pathlib.Path((save_location)),
        }

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
        items = list(self._variables.items())
        for key, val in items:
            if "_" in key:
                new_key = key.replace("_", "")
                self._variables.update({new_key: val})


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
        script_name = await naming_script(dir, file, self._ele)
        if not script_name:
            self._tempfilepath = paths.truncate(pathlib.Path(dir, file))
        else:
            self._tempfilepath = paths.truncate(pathlib.Path(script_name))

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


class Placeholders(basePlaceholder):
    def __init__(self, ele, ext) -> None:
        super().__init__()
        self._filename = None
        self._mediadir = None
        self._metadata = None
        self._filepath = None
        self._ele = ele
        self._ext = ext

    async def init(self, create=True):
        dir = await self.getmediadir(create=create)
        file = await self.createfilename()
        script_name = await naming_script(dir, file, self._ele)
        if not script_name:
            self._filepath = paths.truncate(pathlib.Path(dir, file))
        else:
            self._filepath = paths.truncate(pathlib.Path(script_name))
        return self

    def add_price_variables(self, username):
        modelObj = manager.Manager.current_model_manager.get_model(username)
        self._variables.update(
            {
                "current_price": (
                    of_env.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_current_price == 0 else "Paid"
                )
            }
        )
        self._variables.update(
            {
                "regular_price": (
                    of_env.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_regular_price == 0 else "Paid"
                )
            }
        )
        self._variables.update(
            {
                "promo_price": (
                    of_env.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_promo_price == 0 else "Paid"
                )
            }
        )
        self._variables.update(
            {
                "renewal_price": (
                    of_env.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_renewal_price == 0 else "Paid"
                )
            }
        )

    async def add_common_variables(self, ele, username, model_id):
        await self.add_main_variables(ele, username, model_id)
        self.add_price_variables(username)
        self.add_no_underline()

    async def add_main_variables(self, ele, username, model_id):
        self._variables.update({"user_name": username})
        self._variables.update({"model_id": model_id})
        self._variables.update({"post_id": ele.post_id})
        self._variables.update({"media_id": ele.id})
        self._variables.update({"first_letter": username[0].capitalize()})
        self._variables.update({"media_type": ele.mediatype.capitalize()})
        self._variables.update({"value": ele.value.capitalize()})
        self._variables.update(
            {
                "date": date_placeholder(
                    ele.postdate,
                    ele.date,
                    f"Post {ele.post_id} (media {ele.id})",
                    ele,
                )
            }
        )
        self._variables.update({"model_username": username})
        self._variables.update({"response_type": ele.modified_responsetype})
        self._variables.update({"label": path_safe_label(ele.label_string)})
        self._variables.update({"download_type": ele.downloadtype})
        self._variables.update(
            {"modelObj": manager.Manager.current_model_manager.get_model(username)}
        )
        self._variables.update({"quality": await ele.selected_quality_placeholder})
        self._variables.update({"file_name": await ele.final_filename})
        self._variables.update({"original_filename": ele.filename})
        self._variables.update({"only_file_name": ele.no_quality_final_filename})
        self._variables.update({"only_filename": ele.no_quality_final_filename})
        self._variables.update({"text": ele.file_text})
        self._variables.update({"config": config_file.open_config()})
        self._variables.update({"args": settings.get_args()})

    @basePlaceholder.async_wrapper
    async def getmediadir(self, root=None, create=True):
        if of_env.getattr("SKIP_MEDIADIR_RETRIVAL"):
            return None
        ele = self._ele
        username = ele.username
        model_id = ele.model_id
        type_keys = (ele.responsetype, ele.modified_responsetype, ele.mediatype)
        root, dir_fmt, _ = _resolve_media_templates(type_keys, root=root)
        await self.add_common_variables(ele, username, model_id)
        globals().update(self._variables)
        log.trace(
            f"modelid:{model_id}  mediadir placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        downloadDir = pathlib.Path(dir_fmt.format(**self._variables))
        final_path = pathlib.Path(
            os.path.normpath(f"{str(root)}/{str(pathlib.Path(downloadDir))}")
        )
        log.trace(f"final mediadir path {final_path}")
        self._mediadir = final_path
        self._mediadir.mkdir(parents=True, exist_ok=True) if create else None
        return final_path

    @basePlaceholder.async_wrapper
    async def createfilename(self):
        if of_env.getattr("SKIP_FILENAME_RETRIVAL"):
            return None
        ele = self._ele
        ext = self._ext
        username = ele.username
        model_id = ele.model_id
        type_keys = (ele.responsetype, ele.modified_responsetype, ele.mediatype)
        _, _, file_fmt = _resolve_media_templates(type_keys)
        self._variables.update({"ext": ext})
        await self.add_common_variables(ele, username, model_id)
        globals().update(self._variables)
        log.trace(
            f"model_id:{model_id}  filename placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        out = None
        if ele.responsetype.capitalize() == "Profile":
            out = f"{await ele.final_filename}.{ext}"
        else:
            out = file_fmt.format(**self._variables)
        out = self._addcount(ele, out)
        log.debug(f"final filename path {out}")
        self._filename = out
        return out

    def _addcount(self, ele, out):
        if not of_env.getattr("FILE_COUNT_PLACEHOLDER"):
            return out
        elif not self._needs_count(ele):
            return out
        out = re.sub(" $", "", out)
        # insert count
        if re.search(r"\.(?:[a-zA-Z0-9]+)$", out):
            out = re.sub(r"(\.(?!\.))", f"_{ele.count}.", out)
        else:
            out = f"{out}_{ele.count}"
        return out

    def _needs_count(self, ele):
        unique = set(
            [
                "filename",
                "only_file_name",
                "onlyfilename",
                "original_filename",
                "originalfilename",
                "media_id",
                "mediaid",
            ]
        )
        file_format = parse_safe(data.get_fileformat())
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
        if settings.get_settings().trunicate:
            return pathlib.Path(paths.truncate(self._filepath))
        return self._filepath

    @property
    def trunicated_filedir(self):
        return pathlib.Path(paths.truncate(self._filepath)).parent

    @property
    def size(self):
        if not self.trunicated_filepath:
            return
        elif not self.trunicated_filepath.exists():
            return
        else:
            return self.trunicated_filepath.stat().st_size


class Textholders(basePlaceholder):
    def __init__(self, ele, ext) -> None:
        super().__init__()
        self._filename = None
        self._mediadir = None
        self._metadata = None
        self._filepath = None
        self._ele = ele
        self._ext = ext

    async def init(self, create=True):
        dir = await self.getmediadir(create=create)
        file = await self.createfilename()
        script_name = await naming_script(dir, file, self._ele)
        if not script_name:
            self._filepath = paths.truncate(pathlib.Path(dir, file))
        else:
            self._filepath = paths.truncate(pathlib.Path(script_name))
        return self

    def add_price_variables(self, username):
        modelObj = manager.Manager.current_model_manager.get_model(username)
        self._variables.update(
            {
                "current_price": (
                    of_env.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_current_price == 0 else "Paid"
                )
            }
        )
        self._variables.update(
            {
                "regular_price": (
                    of_env.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_regular_price == 0 else "Paid"
                )
            }
        )
        self._variables.update(
            {
                "promo_price": (
                    of_env.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_promo_price == 0 else "Paid"
                )
            }
        )
        self._variables.update(
            {
                "renewal_price": (
                    of_env.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_renewal_price == 0 else "Paid"
                )
            }
        )

    async def add_common_variables(self, ele, username, model_id):
        await self.add_main_variables(ele, username, model_id)
        self.add_price_variables(username)
        self.add_no_underline()

    async def add_main_variables(self, ele, username, model_id):
        self._variables.update({"user_name": username})
        self._variables.update({"model_id": model_id})
        self._variables.update({"post_id": ele.id})
        self._variables.update({"first_letter": username[0].capitalize()})
        self._variables.update({"value": ele.value.capitalize()})
        self._variables.update(
            {"date": date_placeholder(ele.date, None, f"Post {ele.id}", ele)}
        )
        self._variables.update({"model_username": username})
        self._variables.update({"media_type": "Text"})
        self._variables.update({"response_type": ele.modified_responsetype})
        self._variables.update({"label": path_safe_label(ele.label_string)})
        self._variables.update(
            {"modelObj": manager.Manager.current_model_manager.get_model(username)}
        )
        self._variables.update({"text": ele.text_trunicate(ele.file_sanitized_text)})
        self._variables.update({"config": config_file.open_config()})
        self._variables.update({"args": settings.get_args()})

        sanitized_name = ele.text_trunicate(ele.file_sanitized_text)

        self._variables.update({"quality": "source"})
        self._variables.update({"file_name": sanitized_name})
        self._variables.update({"original_filename": sanitized_name})
        self._variables.update({"only_file_name": sanitized_name})
        self._variables.update({"only_filename": sanitized_name})

    @basePlaceholder.async_wrapper
    async def getmediadir(self, root=None, create=True):
        ele = self._ele
        username = ele.username
        model_id = ele.model_id
        type_keys = (ele.responsetype, ele.modified_responsetype, "text")
        root, dir_fmt, _ = _resolve_media_templates(type_keys, root=root)
        await self.add_common_variables(ele, username, model_id)
        globals().update(self._variables)
        log.trace(
            f"modelid:{model_id}  mediadir placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )

        downloadDir = pathlib.Path(dir_fmt.format(**self._variables))
        final_path = pathlib.Path(
            os.path.normpath(f"{str(root)}/{str(pathlib.Path(downloadDir))}")
        )
        log.trace(f"final mediadir path {final_path}")
        self._mediadir = final_path
        self._mediadir.mkdir(parents=True, exist_ok=True) if create else None
        return final_path

    @basePlaceholder.async_wrapper
    async def createfilename(self):
        ele = self._ele
        ext = self._ext
        username = ele.username
        model_id = ele.model_id
        type_keys = (ele.responsetype, ele.modified_responsetype, "text")
        _, _, file_fmt = _resolve_media_templates(type_keys)
        self._variables.update({"ext": ext})
        await self.add_common_variables(ele, username, model_id)
        globals().update(self._variables)
        log.trace(
            f"model_id:{model_id}  filename placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        out = None
        if ele.responsetype.capitalize() == "Profile":
            text = ele.file_sanitized_text
            text = re.sub(" ", data.get_spacereplacer(), text)
            out = f"{text}.{ext}"
        else:
            out = file_fmt.format(**self._variables)
        log.debug(f"final filename path {out}")
        self._filename = out
        return out

    @property
    def filepath(self):
        return pathlib.Path(self._filepath)

    @property
    def filename(self):
        return pathlib.Path(self._filepath).name

    @property
    def trunicated_filename(self):
        return pathlib.Path(self.trunicated_filepath).name

    @property
    def trunicated_filepath(self):
        if settings.get_settings().trunicate:
            return pathlib.Path(paths.truncate(self._filepath))
        return self._filepath

    @property
    def filedir(self):
        return pathlib.Path(paths.truncate(self._filepath)).parent
