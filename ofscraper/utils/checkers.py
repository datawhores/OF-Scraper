import logging

import ofscraper.data.api.init as init
import ofscraper.sites as sites
import ofscraper.utils.auth.file as auth_file
import ofscraper.utils.auth.make as make

log = logging.getLogger("shared")


class AuthCheckUnavailable(Exception):
    """The auth couldn't be checked (network or server problem)."""


class AuthCheckLeft(Exception):
    """The user chose "Go to Main Menu" in the auth prompt."""


def check_auth(include_main_menu=False):
    status = None
    log.info("checking auth status")
    if sites.is_fansly():
        import ofscraper.sites.fansly.auth as fansly_auth

        fansly_auth.load()
    while status != "UP":
        status = init.getstatus()
        if status == "UNAVAILABLE":
            # the auth may be fine, so don't ask for it again. An ordinary
            # exception ends a one-off run but lets the daemon try its next pass
            raise AuthCheckUnavailable("couldn't check the auth, see the error above")
        if status != "UP":
            log.info("Auth Failed")
            if sites.is_fansly():
                fansly_auth.make_auth()
                continue
            _, choice = make.make_auth(
                auth=auth_file.read_auth(), include_main_menu=include_main_menu
            )
            if choice == "quit":
                raise SystemExit(0)
            if choice == "main":
                # the main menu catches this and shows itself again
                raise AuthCheckLeft("back to the main menu")
        else:
            break
