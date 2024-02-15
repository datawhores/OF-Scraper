import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as config_data


def not_solo_thread():
    return (
        read_args.retriveArgs().downloadthreads != 0 and config_data.get_threads() != 0
    )
