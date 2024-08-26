import logging
import os
import pathlib
import re

import arrow

import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.config.custom as custom_
import ofscraper.utils.config.data as data
import ofscraper.utils.config.file as config_file
import ofscraper.utils.constants as constants
import ofscraper.utils.me as me
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.paths.paths as paths
import ofscraper.utils.profiles.data as profile_data
import ofscraper.utils.settings as settings
from ofscraper.utils.string import parse_safe
import  ofscraper.runner.manager as manager


log = logging.getLogger("shared")


def check_uniquename():
    format = data.get_fileformat()
    if re.search("text", format):
        return True
    elif re.search("filename", format):
        return True
    elif re.search("post_id", format):
        return True
    elif re.search("postid", format):
        return True
    elif re.search("media_id", format):
        return True
    elif re.search("mediaid", format):
        return True
    elif re.search("custom", format):
        return True
    return False


class basePlaceholder:
    def __init__(self) -> None:
        self._ele = None

    def create_variables_base(self):
        my_id, my_username = me.parse_user()
        self._variables = {
            "config_path": common_paths.get_config_home(),
            "profile": profile_data.get_active_profile(),
            "site_name": "Onlyfans",
            "save_location": common_paths.get_save_location(mediatype=self._ele),
            "my_id": my_id,
            "my_username": my_username,
            "root": pathlib.Path((common_paths.get_save_location(mediatype=self._ele))),
            "customval": custom_.get_custom(),
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
            if key.find("_"):
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
        # if constants.getattr("ALLOW_DUPE_MEDIA"):
        #     file=f"{''.join(random.choice(string.ascii_letters + string.digits) for _ in range(6))}{file}"
        self._tempfilepath = paths.truncate(pathlib.Path(dir, file))
        return self

    @basePlaceholder.async_wrapper
    async def gettempDir(self, ele, create=True):
        self._tempdir = await self._placeholder.getmediadir(
            root=(data.get_TempDir(mediatype=ele.mediatype)),
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
    def __init__(self) -> None:
        super().__init__()

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
        if data.get_allow_code_execution():
            if isinstance(customval, dict) is False:
                try:
                    custom = eval(customval)
                except:
                    custom = {}
            else:
                custom = {}
                for key, val in customval.items():
                    try:
                        custom[key] = eval(val)
                    except:
                        custom[key] = val

            formatStr = eval("f'{}'".format(data.get_metadata()))

        else:
            formatStr = data.get_metadata().format(**self._variables)
        data_path = pathlib.Path(formatStr, "user_data.db")
        data_path = pathlib.Path(os.path.normpath(data_path))
        self._metadata = data_path
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
        self._matadata = input

class Placeholders(basePlaceholder):
    def __init__(self, ele, ext) -> None:
        super().__init__()
        self._filename = None
        self._mediadir = None
        self._metadata = None
        self._filepath = None
        self._ele = ele
        self._ext = ext

    async def init(self,create=True):
        dir = await self.getmediadir(create=create)
        file = await self.createfilename()
        self._filepath = paths.truncate(pathlib.Path(dir, file))
        return self

    def add_price_variables(self, username):
        modelObj = manager.Manager.model_manager.get_model(username)
        self._variables.update(
            {
                "current_price": (
                    constants.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_current_price == 0 else "Paid"
                )
            }
        )
        self._variables.update(
            {
                "regular_price": (
                    constants.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_regular_price == 0 else "Paid"
                )
            }
        )
        self._variables.update(
            {
                "promo_price": (
                    constants.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_promo_price == 0 else "Paid"
                )
            }
        )
        self._variables.update(
            {
                "renewal_price": (
                    constants.getattr("MODEL_PRICE_PLACEHOLDER")
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
        self._variables.update({"post_id": ele.postid})
        self._variables.update({"media_id": ele.id})
        self._variables.update({"first_letter": username[0].capitalize()})
        self._variables.update({"media_type": ele.mediatype.capitalize()})
        self._variables.update({"value": ele.value.capitalize()})
        self._variables.update(
            {
                "date": arrow.get(ele.postdate).format(
                    data.get_date(mediatype=ele.mediatype)
                )
            }
        )
        self._variables.update({"model_username": username})
        self._variables.update({"response_type": ele.modified_responsetype})
        self._variables.update({"label": ele.label_string})
        self._variables.update({"download_type": ele.downloadtype})
        self._variables.update({"modelObj": manager.Manager.model_manager.get_model(username)})
        self._variables.update({"quality": await ele.selected_quality_placeholder})
        self._variables.update({"file_name": await ele.final_filename})
        self._variables.update({"original_filename": ele.filename})
        self._variables.update({"only_file_name": ele.no_quality_final_filename})
        self._variables.update({"only_filename": ele.no_quality_final_filename})
        self._variables.update({"text": ele.file_text})
        self._variables.update({"config": config_file.open_config()})
        self._variables.update({"args": read_args.retriveArgs()})

    @basePlaceholder.async_wrapper
    async def getmediadir(self, root=None, create=True):
        ele = self._ele
        username = ele.username
        model_id = ele.model_id
        root = pathlib.Path(root or common_paths.get_save_location(mediatype=self._ele))
        await self.add_common_variables(ele, username, model_id)
        globals().update(self._variables)
        log.trace(
            f"modelid:{model_id}  mediadir placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        if data.get_allow_code_execution():
            if isinstance(customval, dict) is False:
                try:
                    custom = eval(customval)
                except:
                    custom = {}
            else:
                custom = {}
                for key, val in customval.items():
                    try:
                        custom[key] = eval(val)
                    except:
                        custom[key] = val
            downloadDir = pathlib.Path(
                eval("f'{}'".format(data.get_dirformat(mediatype=ele.mediatype)))
            )
        else:
            downloadDir = pathlib.Path(
                data.get_dirformat(mediatype=ele.mediatype).format(**self._variables)
            )
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
        self._variables.update({"ext": ext})
        await self.add_common_variables(ele, username, model_id)
        globals().update(self._variables)
        log.trace(
            f"modelid:{model_id}  filename placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        out = None
        if ele.responsetype == "profile":
            out = f"{await ele.final_filename}.{ext}"
        elif data.get_allow_code_execution():
            if isinstance(customval, dict) is False:
                try:
                    custom = eval(customval)
                except:
                    custom = {}
            else:
                custom = {}
                for key, val in customval.items():
                    try:
                        custom[key] = eval(val)
                    except:
                        custom[key] = val
            out = eval('f"""{}"""'.format(data.get_fileformat(mediatype=ele.mediatype)))
        else:
            out = data.get_fileformat(mediatype=ele.mediatype).format(**self._variables)
        out = self._addcount(ele, out)
        log.debug(f"final filename path {out}")
        self._filename = out
        return out

    def _addcount(self, ele, out):
        if not constants.getattr("FILE_COUNT_PLACEHOLDER"):
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
        elif len(ele._post.post_media) > 1 or ele.responsetype in [
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
        if settings.get_trunication(mediatype=self._ele.mediatype):
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

    async def init(self,create=True):
        dir = await self.getmediadir(create=create)
        file = await self.createfilename()
        self._filepath = paths.truncate(pathlib.Path(dir, file))
        return self

    def add_price_variables(self, username):
        modelObj = manager.Manager.model_manager.get_model(username)
        self._variables.update(
            {
                "current_price": (
                    constants.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_current_price == 0 else "Paid"
                )
            }
        )
        self._variables.update(
            {
                "regular_price": (
                    constants.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_regular_price == 0 else "Paid"
                )
            }
        )
        self._variables.update(
            {
                "promo_price": (
                    constants.getattr("MODEL_PRICE_PLACEHOLDER")
                    if not modelObj
                    else "Free" if modelObj.final_promo_price == 0 else "Paid"
                )
            }
        )
        self._variables.update(
            {
                "renewal_price": (
                    constants.getattr("MODEL_PRICE_PLACEHOLDER")
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
            {"date": arrow.get(ele.date).format(data.get_date(mediatype="Text"))}
        )
        self._variables.update({"model_username": username})
        self._variables.update({"media_type": "Text"})
        self._variables.update({"response_type": ele.modified_responsetype})
        self._variables.update({"label": ele.label_string})
        self._variables.update({"modelObj": manager.Manager.model_manager.get_model(username)})
        self._variables.update({"text": ele.text_trunicate(ele.file_sanitized_text)})
        self._variables.update({"config": config_file.open_config()})
        self._variables.update({"args": read_args.retriveArgs()})

        self._variables.update({"quality": "source"})
        self._variables.update(
            {"file_name": f"{ele.text_trunicate(ele.file_sanitized_text)}_source"}
        )
        self._variables.update(
            {"original_filename": ele.text_trunicate(ele.file_sanitized_text)}
        )
        self._variables.update(
            {"only_file_name": ele.text_trunicate(ele.file_sanitized_text)}
        )

    @basePlaceholder.async_wrapper
    async def getmediadir(self, root=None, create=True):
        ele = self._ele
        username = ele.username
        model_id = ele.model_id
        root = pathlib.Path(root or common_paths.get_save_location(mediatype="Text"))
        await self.add_common_variables(ele, username, model_id)
        globals().update(self._variables)
        log.trace(
            f"modelid:{model_id}  mediadir placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        if data.get_allow_code_execution():
            if isinstance(customval, dict) is False:
                try:
                    custom = eval(customval)
                except:
                    custom = {}
            else:
                custom = {}
                for key, val in customval.items():
                    try:
                        custom[key] = eval(val)
                    except:
                        custom[key] = val
            downloadDir = pathlib.Path(
                eval("f'{}'".format(data.get_dirformat(mediatype="Text")))
            )
        else:
            downloadDir = pathlib.Path(
                data.get_dirformat(mediatype="Text").format(**self._variables)
            )
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
        self._variables.update({"ext": ext})
        await self.add_common_variables(ele, username, model_id)
        globals().update(self._variables)
        log.trace(
            f"modelid:{model_id}  filename placeholders {filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items()))}"
        )
        out = None
        if ele.responsetype == "profile":
            text = ele.file_sanitized_text
            text = re.sub(" ", data.get_spacereplacer(mediatype="Text"), text)
            out = f"{text}.{ext}"
        elif data.get_allow_code_execution():
            if isinstance(customval, dict) is False:
                try:
                    custom = eval(customval)
                except:
                    custom = {}
            else:
                custom = {}
                for key, val in customval.items():
                    try:
                        custom[key] = eval(val)
                    except:
                        custom[key] = val
            out = eval('f"""{}"""'.format(data.get_fileformat(mediatype="Text")))
        else:
            out = data.get_fileformat(mediatype="Text").format(**self._variables)
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
        if settings.get_trunication(mediatype=self._ele.mediatype):
            return pathlib.Path(paths.truncate(self._filepath))
        return self._filepath

    @property
    def filedir(self):
        return pathlib.Path(paths.truncate(self._filepath)).parent
