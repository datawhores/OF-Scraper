import ofscraper.utils.env.env as env

import ofscraper.utils.settings as settings


def in_check_mode():
    return settings.get_settings().command.find("_check") != -1


def get_download_retries():
    return (
        env.getattr("DOWNLOAD_NUM_TRIES")
        if not in_check_mode()
        else env.getattr("DOWNLOAD_NUM_TRIES_CHECK")
    )


def get_download_req_retries():
    return (
        env.getattr("DOWNLOAD_NUM_TRIES_REQ")
        if not in_check_mode()
        else env.getattr("DOWNLOAD_NUM_TRIES_CHECK_REQ")
    )


def get_cmd_download_req_retries():
    return (
        env.getattr("CDM_NUM_TRIES")
        if not in_check_mode()
        else env.getattr("CDM_NUM_TRIES_CHECK")
    )
