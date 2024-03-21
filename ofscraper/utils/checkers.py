import logging
from contextlib import contextmanager

import ofscraper.api.init as init
import ofscraper.utils.auth.file as auth_file
import ofscraper.utils.auth.make as make
import ofscraper.utils.config.config as config_
import ofscraper.utils.config.data as data
import ofscraper.utils.console as console
import ofscraper.utils.paths.check as check
import ofscraper.utils.settings as settings

log = logging.getLogger("shared")


def check_auth():
    status = None
    while status != "UP":
        status = init.getstatus()
        if status == "DOWN":
            log.warning("Auth Failed")
            make.make_auth(auth=auth_file.read_auth())
            continue
        break


def check_config():
    while not check.mp4decryptchecker(settings.get_mp4decrypt()):
        console.get_shared_console().print(
            "There is an issue with the mp4decrypt path\n\n"
        )
        log.debug(f"[bold]current mp4decrypt path[/bold] {settings.get_mp4decrypt()}")
        config_.update_mp4decrypt()
    while not check.ffmpegchecker(settings.get_ffmpeg()):
        console.get_shared_console().print("There is an issue with the ffmpeg path\n\n")
        log.debug(f"[bold]current ffmpeg path[/bold] {settings.get_ffmpeg()}")
        config_.update_ffmpeg()
    log.debug(f"[bold]final mp4decrypt path[/bold] {settings.get_mp4decrypt()}")
    log.debug(f"[bold]final ffmpeg path[/bold] {settings.get_ffmpeg()}")


def check_config_key_mode():
    if settings.get_key_mode() == "keydb" and not data.get_keydb_api():
        console.shared_console.print(
            "[red]You must setup keydb API Key\nhttps://keysdb.net[/red]"
        )
