import ofscraper.utils.settings as settings


def is_trace():
    return (
        settings.get_settings().discord_level == "TRACE"
        or settings.get_settings().log_level == "TRACE"
        or settings.get_settings().output_level == "TRACE"
    )
