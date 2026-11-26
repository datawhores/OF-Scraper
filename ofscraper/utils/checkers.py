import logging

import ofscraper.data.api.init as init
import ofscraper.sites as sites
import ofscraper.utils.auth.file as auth_file
import ofscraper.utils.auth.make as make
import ofscraper.utils.interactive as interactive

log = logging.getLogger("shared")


class AuthCheckUnavailable(Exception):
    """The auth couldn't be checked (network, server or dynamic rule problem).

    The message says why, so a caller can show it without the log.
    """


class AuthCheckLeft(Exception):
    """The user chose "Go to Main Menu" in the auth prompt."""


def check_auth(include_main_menu=False):
    status = None
    log.info("checking auth status")
    if sites.is_fansly():
        import ofscraper.sites.fansly.auth as fansly_auth

        fansly_auth.load()
    while status != "UP":
        status, message = init.auth_status()
        if status == "UNAVAILABLE":
            # the auth may be fine, so don't ask for it again. An ordinary
            # exception ends a one-off run but lets the daemon try its next pass
            raise AuthCheckUnavailable(f"Couldn't check the auth: {message}")
        if status != "UP":
            log.info("Auth Failed")
            try:
                if sites.is_fansly():
                    fansly_auth.make_auth()
                    continue
                _, choice = make.make_auth(
                    auth=auth_file.read_auth(), include_main_menu=include_main_menu
                )
            except interactive.NoConsoleError as e:
                # no one can answer the auth prompt (a scheduled run, a
                # --profiles child): end with "login failed", not the
                # generic error
                import ofscraper.main.close.exit_status as exit_status

                log.error(
                    f"{'Fansly' if sites.is_fansly() else 'OnlyFans'} rejected"
                    " the login, and there's no"
                    " interactive console to ask for new auth. Update the auth"
                    " file, or run in a terminal."
                )
                raise SystemExit(exit_status.AUTH) from e
            if choice == "quit":
                raise SystemExit(0)
            if choice == "main":
                # the main menu catches this and shows itself again
                raise AuthCheckLeft("back to the main menu")
        else:
            break
