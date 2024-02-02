import pathlib

import ofscraper.const.constants as consts
import ofscraper.utils.args.read as read_args


def get_config_home():
    return get_config_path().parent


def get_config_path():
    configPath = read_args.retriveArgs().config
    defaultPath = pathlib.Path.home() / consts.configPath / consts.configFile
    ofscraperHome = pathlib.Path.home() / consts.configPath

    if configPath == None or configPath == "":
        return defaultPath
    configPath = pathlib.Path(configPath)
    # check if path exists
    if configPath.is_file():
        return configPath
    elif configPath.is_dir():
        return configPath / consts.configFile
    # enforce that configpath needs some extension
    elif configPath.suffix == "":
        return configPath / consts.configFile

    elif str(configPath.parent) == ".":
        return ofscraperHome / configPath
    return configPath
