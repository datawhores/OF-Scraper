import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as config_data


def get_max_count():
    return read_args.retriveArgs().max_count or config_data.get_max_post_count() or None
