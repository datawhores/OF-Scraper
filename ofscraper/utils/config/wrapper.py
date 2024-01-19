from collections import abc

import ofscraper.utils.config.file as config_file


def config_reader(func: abc.Callable):
    def inner(*arg, **kwargs):
        config = config_file.open_config()
        return func(config=config)

    return inner
