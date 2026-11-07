import logging

import ofscraper.data.api.init as init
import ofscraper.utils.auth.file as auth_file
import ofscraper.utils.auth.make as make

log = logging.getLogger("shared")


class AuthCheckUnavailable(Exception):
    """The auth couldn't be checked (network or server problem)."""


def check_auth():
    status = None
    log.info("checking auth status")
    while status != "UP":
        status = init.getstatus()
        if status == "UNAVAILABLE":
            # the auth may be fine, so don't ask for it again. An ordinary
            # exception ends a one-off run but lets the daemon try its next pass
            raise AuthCheckUnavailable("couldn't check the auth, see the error above")
        if status != "UP":
            log.info("Auth Failed")
            make.make_auth(auth=auth_file.read_auth())
        else:
            break
