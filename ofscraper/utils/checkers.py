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


class LoginRejected(Exception):
    """The site rejected the login partway through a run; the pass stops."""


# whether this pass has asked auth_status after a failure already
_login_checked = False


def new_pass():
    global _login_checked
    _login_checked = False


def http_status(error):
    """The HTTP status an error carries, from any of the clients, or None."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        for value in (
            getattr(error, "status", None),
            getattr(getattr(error, "response", None), "status_code", None),
            getattr(getattr(error, "response", None), "status", None),
        ):
            if isinstance(value, int):
                return value
        error = error.__cause__ or error.__context__
    return None


def check_login_after_failure(error):
    """After a creator failed with 401 or 403, ask once per pass whether the
    login still works: a 403 can also be a rate or location block, so the
    status alone isn't trusted. If the site says the login is rejected, the
    pass stops with "login failed" and an alert."""
    global _login_checked
    if _login_checked or http_status(error) not in (401, 403):
        return
    _login_checked = True
    status, _ = init.auth_status()
    if status != "DOWN":
        return
    import ofscraper.main.close.alerts as alerts
    import ofscraper.main.close.exit_status as exit_status
    import ofscraper.main.close.status_file as status_file

    exit_status.record(exit_status.AUTH)
    status_file.set_auth("failed")
    alerts.failing(alerts.LOGIN, f"{_site_label()} rejected the login during the run; update the auth")
    raise LoginRejected(f"{_site_label()} rejected the login") from error


def _site_label():
    return "Fansly" if sites.is_fansly() else "OnlyFans"


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
            import ofscraper.main.close.alerts as alerts
            import ofscraper.main.close.status_file as status_file

            status_file.set_auth("failed")
            # before any prompt: in a daemon under Docker's tty: true a
            # prompt waits forever, so at least the wait is announced
            alerts.failing(alerts.LOGIN, f"{_site_label()} rejected the login; update the auth")
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
            import ofscraper.main.close.alerts as alerts
            import ofscraper.main.close.status_file as status_file

            status_file.set_auth("ok")
            alerts.recovered(alerts.LOGIN, f"{_site_label()} login works again")
            break
