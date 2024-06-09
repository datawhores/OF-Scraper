import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants


def in_check_mode():
    return read_args.retriveArgs().command.find("_check") != -1


def get_download_retries():
    return (
        constants.getattr("DOWNLOAD_NUM_TRIES")
        if not in_check_mode()
        else constants.getattr("DOWNLOAD_NUM_TRIES_CHECK")
    )


def get_download_req_retries():
    return (
        constants.getattr("DOWNLOAD_NUM_TRIES_REQ")
        if not in_check_mode()
        else constants.getattr("DOWNLOAD_NUM_TRIES_CHECK_REQ")
    )


def get_cmd_download_req_retries():
    return (
        constants.getattr("CDM_NUM_TRIES")
        if not in_check_mode()
        else constants.getattr("CDM_NUM_TRIES_CHECK")
    )
