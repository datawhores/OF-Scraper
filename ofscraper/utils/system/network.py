import logging

import ofscraper.utils.console as console_
import ofscraper.utils.settings as settings

CDRM_DEPRECATED = (
    "Key mode cdrm is deprecated and will be removed: its service, "
    "cdrm-project.com, no longer works, so DRM videos can't be decrypted with it. "
    "Use key mode manual with your own CDM files: "
    "https://cloakedkeys.gitbook.io/ofsc/cdm-options"
)


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
        import ofscraper.commands.scraper.actions.download.utils.keyhelpers as keyhelpers

        missing = keyhelpers.missing_cdm_keys()
        if missing:
            # shown even with --no-rich or low output: it explains the skips
            alert.print(
                f"[yellow]CDM keys not detected ({missing}).\n"
                "This may affect the download of files with DRM: they're skipped "
                "until client-id and private-key are set under cdm_options.\n"
                "https://cloakedkeys.gitbook.io/ofsc/cdm-options\n[/yellow]"
            )
            # debug: the console already shows it
            log.debug(f"CDM keys not detected ({missing}); DRM files will be skipped")
            return True
        console.print(
            "[yellow]WARNING:Make sure you have all the correct settings for choosen cdm\nhttps://cloakedkeys.gitbook.io/ofsc/cdm-options\n\n[/yellow]"
        )
        return True
    elif keymode == "cdrm":
        import ofscraper.commands.scraper.actions.download.utils.keyhelpers as keyhelpers

        message = CDRM_DEPRECATED
        if keyhelpers.cdrm_unavailable():
            # the default address: nothing is sent, and the videos aren't
            # downloaded, as they can't get a key (#681)
            message = (
                "Nothing is sent to cdrm-project.com, so DRM videos are skipped "
                f"before download. {CDRM_DEPRECATED}"
            )
        alert.print(f"[red]{message}\n[/red]")
        # debug: the console already shows it
        log.debug(message)
    # cdrm's service no longer works, so there's nothing to probe
    return False
