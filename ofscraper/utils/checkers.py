import logging
from contextlib import contextmanager

import ofscraper.api.init as init
import ofscraper.utils.auth as auth
import ofscraper.utils.config.config as config_
import ofscraper.utils.config.data as data
import ofscraper.utils.console as console
import ofscraper.utils.paths.check as check

log = logging.getLogger("shared")


def check_auth():
    status = None
    while status != "UP":
        status = init.getstatus()
        if status == "DOWN":
            log.warning("Auth Failed")
            auth.make_auth(auth=auth.read_auth())
            continue
        break


def check_config():
    while not check.mp4decryptchecker(data.get_mp4decrypt()):
        console.get_shared_console().print(
            "There is an issue with the mp4decrypt path\n\n"
        )
        log.debug(f"[bold]current mp4decrypt path[/bold] {data.get_mp4decrypt()}")
        config_.update_mp4decrypt()
    while not check.ffmpegchecker(data.get_ffmpeg()):
        console.get_shared_console().print("There is an issue with the ffmpeg path\n\n")
        log.debug(f"[bold]current ffmpeg path[/bold] {data.get_ffmpeg()}")
        config_.update_ffmpeg()
    log.debug(f"[bold]final mp4decrypt path[/bold] {data.get_mp4decrypt()}")
    log.debug(f"[bold]final ffmpeg path[/bold] {data.get_ffmpeg()}")
