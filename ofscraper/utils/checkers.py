import logging

import ofscraper.data.api.init as init
import ofscraper.utils.auth.file as auth_file
import ofscraper.utils.auth.make as make
import ofscraper.utils.console as console
import ofscraper.utils.settings as settings


log = logging.getLogger("shared")


def check_auth():
    status = None
    log.info("checking auth status")
    while status != "UP":
        status = init.getstatus()
        if status != "UP":
            log.warning("Auth Failed")
            make.make_auth(auth=auth_file.read_auth())
        break



