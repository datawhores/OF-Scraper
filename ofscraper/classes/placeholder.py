import logging
import os
import pathlib
import re

import arrow

import ofscraper.models.selector as selector
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.config.custom as custom_
import ofscraper.utils.config.data as data
import ofscraper.utils.config.file as config_file
import ofscraper.utils.constants as constants
import ofscraper.utils.me as me
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.paths.paths as paths
import ofscraper.utils.profiles.data as profile_data

log = logging.getLogger("shared")


class Placeholders:
    def __init__(self) -> None:
        None
        self._filename = None
        self._mediadir = None
        self._metadata = None
        self._tempdir = None
        self._final_path = None
        self._tempfilename = None

    def wrapper(f):
        def wrapper(*args, **kwargs):
            args[0]._variables = {}
            args[0].create_variables_base()
            return f(args[0], *args[1:], **kwargs)

        return wrapper

    def create_variables_base(self):
        my_profile = profile_data.get_my_info()
        my_id, my_username = me.parse_user(my_profile)

        self._variables = {
            "configpath": common_paths.get_config_home(),
            "profile": profile_data.get_active_profile(),
            "sitename": "Onlyfans",
            "site_name": "Onlyfans",
            "save_location": common_paths.get_save_location(),
            "my_id": my_id,
            "my_username": my_username,
            "root": pathlib.Path((common_paths.get_save_location())),
            "customval": custom_.get_custom(),
        }

    def add_price_variables(self, username):
        modelObj = selector.get_model_fromParsed(username)
        current_price = (
            constants.getattr("MODEL_PRICE_PLACEHOLDER")
            if not modelObj
            else "Free"
            if modelObj.final_current_price == 0
            else "Paid"
        )

        self._variables.update({"current_price": current_price})
        self._variables.update({"currentprice": current_price})
        regular_price = (
            constants.getattr("MODEL_PRICE_PLACEHOLDER")
            if not modelObj
            else "Free"
            if modelObj.final_regular_price == 0
            else "Paid"
        )
        self._variables.update({"regular_price": regular_price})
        self._variables.update({"regularprice": regular_price})
        promo_price = (
            constants.getattr("MODEL_PRICE_PLACEHOLDER")
            if not modelObj
            else "Free"
            if modelObj.final_promo_price == 0
            else "Paid"
        )
        self._variables.update({"promo_price": promo_price})
        self._variables.update({"promoprice": promo_price})
        renewal_price = (
            constants.getattr("MODEL_PRICE_PLACEHOLDER")
            if not modelObj
            else "Free"
            if modelObj.final_renewal_price == 0
            else "Paid"
        )
        self._variables.update({"renewal_price": renewal_price})
        self._variables.update({"renewalprice": renewal_price})

    def add_common_variables(self, ele, username, model_id):
        self._variables.update({"username": username})
        self._variables.update({"user_name": username})
        self._variables.update({"model_id": model_id})
        self._variables.update({"modelid": model_id})
        post_id = ele.postid
        self._variables.update({"post_id": post_id})
        self._variables.update({"postid": post_id})
        media_id = ele.id
        self._variables.update({"media_id": media_id})
        self._variables.update({"mediaid": media_id})
        first_letter = username[0].capitalize()
        self._variables.update({"first_letter": first_letter})
        self._variables.update({"firstletter": first_letter})
        mediatype = ele.mediatype.capitalize()
        self._variables.update({"mediatype": mediatype})
        self._variables.update({"media_type": mediatype})
        value = ele.value.capitalize()
        self._variables.update({"value": value})
        date = arrow.get(ele.postdate).format(data.get_date())
        self._variables.update({"date": date})
        model_username = username
        self._variables.update({"model_username": model_username})
        self._variables.update({"modelusername": model_username})
        responsetype = ele.modified_responsetype
        self._variables.update({"responsetype": responsetype})
        self._variables.update({"response_type": responsetype})
        label = ele.label_string
        self._variables.update({"label": label})
        downloadtype = ele.downloadtype
        self._variables.update({"downloadtype": downloadtype})
        self._variables.update({"download_type": downloadtype})
        self._variables.update({"media_id": media_id})
        self._variables.update({"mediaid": media_id})
        self._variables.update({"modelObj": selector.get_model_fromParsed(username)})
        self._variables.update({"quality": ele.selected_quality})
        self._variables.update({"filename": ele.final_filename})
        self._variables.update({"file_name": ele.final_filename})
        self._variables.update({"only_file_name": ele.no_quality_final_filename})
        self._variables.update({"only_filename": ele.no_quality_final_filename})
        self._variables.update({"text": ele.file_text})
        self._variables.update({"config": config_file.open_config()})
        self._variables.update({"args": read_args.retriveArgs()})

        self.add_price_variables(username)

    @wrapper
    def databasePathHelper(self, model_id, model_username):
        username = model_username
        self._variables.update({"username": username})
        modelusername = model_username
        self._variables.update({"modelusername": modelusername})
        model_username = model_username
        self._variables.update({"model_username": model_username})
        first_letter = username[0].capitalize()
        self._variables.update({"first_letter": first_letter})
        firstletter = username[0].capitalize()
        self._variables.update({"firstletter": firstletter})
        self._variables.update({"model_id": model_id})
        modelid = model_id
        self._variables.update({"modelid": modelid})
        globals().update(self._variables)
        log.trace(
            f"modelid:{model_id}  database placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        if data.get_allow_code_execution():
            if isinstance(customval, dict) == False:
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
        cache.close()
        return pathlib.Path(
            re.sub(
                "user_data.db",
                f"/backup/user_data_copy_{counter}.db",
                str(self.databasePathHelper(model_id, model_username)),
            )
        )

    @wrapper
    def gettempDir(self, ele, username, model_id, create=True):
        self._tempdir = self.getmediadir(
            ele,
            username,
            model_id,
            root=(data.get_TempDir()),
            create=create,
        )
        self._tempdir.mkdir(parents=True, exist_ok=True)
        return self._tempdir

    @wrapper
    def getmediadir(self, ele, username, model_id, root=None, create=True):
        root = pathlib.Path(root or common_paths.get_save_location())
        self.add_common_variables(ele, username, model_id)
        globals().update(self._variables)
        log.trace(
            f"modelid:{model_id}  mediadir placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        if data.get_allow_code_execution():
            if isinstance(customval, dict) == False:
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
            downloadDir = pathlib.Path(eval("f'{}'".format(data.get_dirformat())))
        else:
            downloadDir = pathlib.Path(data.get_dirformat().format(**self._variables))
        final_path = pathlib.Path(
            os.path.normpath(f"{str(root)}/{str(pathlib.Path(downloadDir))}")
        )
        log.trace(f"final mediadir path {final_path}")
        self._mediadir = final_path
        self._mediadir.mkdir(parents=True, exist_ok=True) if create else None
        return final_path

    @wrapper
    def createfilename(self, ele, username, model_id, ext):
        self._variables.update({"ext": ext})
        self.add_common_variables(ele, username, model_id)
        globals().update(self._variables)
        log.trace(
            f"modelid:{model_id}  filename placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}"
        )
        out = None
        if ele.responsetype == "profile":
            out = f"{ele.final_filename}.{ext}"
        elif data.get_allow_code_execution():
            if isinstance(customval, dict) == False:
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
            out = eval('f"""{}"""'.format(data.get_fileformat()))
        else:
            out = data.get_fileformat().format(**self._variables)
        out = self._addcount(ele, out)
        log.debug(f"final filename path {out}")
        self._filename = out
        return out

    def _addcount(self, ele, out):
        if not ele.needs_count:
            return out
        out = re.sub(" $", "", out)
        out = re.sub("( *\.(?!\.))", f".", out)
        # insert count
        if re.search("\.[^.]+", out):
            out = re.sub("(\.(?!\.))", f"_{ele.count}.", out)
        else:
            out = f"{out}_{ele.count}"
        return out

    def set_final_path(self):
        if (read_args.retriveArgs().original or data.get_truncation()) is False:
            self._final_path = pathlib.Path(self.mediadir, f"{self.filename}")
        elif read_args.retriveArgs().original is False:
            self._final_path = pathlib.Path(self.mediadir, f"{self.filename}")
        elif read_args.retriveArgs().original is True or data.get_truncation() is True:
            self._final_path = paths.truncate(
                pathlib.Path(self.mediadir, f"{self.filename}")
            )

    def getDirs(self, ele, username, model_id, create=True):
        self.gettempDir(ele, username, model_id, create=create)
        self.getmediadir(ele, username, model_id, create=create)

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, input):
        self._filename = input

    @property
    def mediadir(self):
        return self._mediadir

    @mediadir.setter
    def mediadir(self, input):
        self._mediadir = input

    @property
    def tempdir(self):
        return self._tempdir

    @tempdir.setter
    def tempdir(self, input):
        self._tempdir = input

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, input):
        self._matadata = input

    @property
    def trunicated_filename(self):
        return self._final_path

    @trunicated_filename.setter
    def trunicated_filename(self, input):
        self._final_path = input

    @property
    def tempfilename(self):
        return self._tempfilename

    @tempfilename.setter
    def tempfilename(self, input):
        self._tempfilename = paths.truncate(pathlib.Path(self._tempdir, input))

    def check_uniquename(self):
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


# def all_placeholders():
#       {"user_name","modelid","model_id","username","postid","postid","media_id",
#        "mediaid","first_letter","firstletter","mediatype","media_type","value","date",
#        "model_username","modelusername","response_type","responsetype","label","downloadtype","download_type"}
