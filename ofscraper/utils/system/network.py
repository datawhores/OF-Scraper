import logging
import time
import traceback

import httpx

import ofscraper.managers.sessionmanager.sessionmanager as sessionManager
import ofscraper.utils.console as console_
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings


def check_cdm():
    console = console_.get_shared_console()
    # failures are shown even when --output quiets the shared console
    alert = console_.get_console()
    log = logging.getLogger("shared")

    import ofscraper.sites as sites

    if sites.is_fansly():
        # Fansly video has no DRM, so there is no CDM to check
        return True
    keymode = settings.get_settings().key_mode
    console.print(f"[yellow]Key Mode: {keymode}\n\n[/yellow]")
    if keymode == "manual":
        console.print(
            "[yellow]WARNING:Make sure you have all the correct settings for choosen cdm\nhttps://cloakedkeys.gitbook.io/ofsc/cdm-options\n\n[/yellow]"
        )
        return True
    elif keymode == "cdrm":
        url = of_env.getattr("CDRM")
    try:
        with sessionManager.sessionManager(
            total_timeout=of_env.getattr("CDM_TEST_TIMEOUT"),
            retries=of_env.getattr("CDM_TEST_NUM_TRIES"),
            wait_min=of_env.getattr("CDM_MIN_WAIT"),
            wait_max=of_env.getattr("CDM_MAX_WAIT"),
        ) as c:
            with c.requests(url=url, headers={}) as r:
                # the cdrm decrypt endpoint only accepts POST, so a GET
                # answering 405 means it is there
                if r.ok or (keymode == "cdrm" and r.status == 405):
                    console.print("[green] CDM service seems to be working\n[/green]")
                    console.print(
                        "[yellow]WARNING:Make sure you have all the correct settings for choosen cdm\nhttps://cloakedkeys.gitbook.io/ofsc/cdm-options\n\n[/yellow]"
                    )
                    return True
                else:
                    alert.print(
                        "[red]CDM return an error\nThis may cause a lot of failed downloads\n consider switching\nhttps://cloakedkeys.gitbook.io/ofsc/cdm-options\n\n[/red]"
                    )
                    log.debug(f"[bold] cdm status[/bold]: {r.status}")
                    log.debug(f"[bold]  cdm text [/bold]: {r.text_()}")
                    log.debug(f"[bold]  cdm headers [/bold]: {r.headers}")
                    time.sleep(3.5)
                    return False
    except httpx.TimeoutException:
        alert.print(
            f"[red]CDM service {keymode} timed out and seems to be down\nThis may cause a lot of failed downloads\nPlease confirm by checking the url:{url}\n Consider switching\nhttps://cloakedkeys.gitbook.io/ofsc/cdm-options\n\n[/red]"
        )
        log.debug(traceback.format_exc())
        time.sleep(3.5)

    except Exception as E:
        alert.print(
            f"[red]CDM service {keymode} has an issue {E}\nThis may cause a lot of failed downloads\nPlease confirm by checking the url:{url}\n Consider switching\nhttps://cloakedkeys.gitbook.io/ofsc/cdm-options\n\n[/red]"
        )
        log.debug(traceback.format_exc())
        time.sleep(3.5)
    return False
