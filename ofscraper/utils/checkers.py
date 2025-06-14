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
            continue
        break




def check_config_key_mode():
    if (
        settings.get_settings().key_mode == "keydb"
        and not settings.get_settings().keydb_api()
    ):
        console.shared_console.print(
            "[red]You must setup keydb API Key\nhttps://keysdb.net[/red]"
        )
