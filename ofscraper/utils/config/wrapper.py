from collections import abc

import ofscraper.utils.config.file as config_file


def config_reader(func: abc.Callable):
    def inner(**kwargs):
        config = kwargs.pop("config", None)
        configT = (
            False
            if config == False
            else config
            if config != None
            else config_file.open_config()
        )
        return func(config=configT)

    return inner
