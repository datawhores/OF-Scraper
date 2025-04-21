import ofscraper.utils.args.accessors.read as read_args


def get_command():
    return settings.get_settings().command
