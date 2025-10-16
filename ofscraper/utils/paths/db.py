import pathlib

from ofscraper.utils.paths.common import get_profile_path


def get_all_db(db_path):
    all_files = pathlib.Path(db_path).rglob("*")
    filtered_files = filter(lambda x: x.is_file(), all_files)
    filtered_files = filter(lambda x: x.name == "user_data.db", all_files)
    return filtered_files


def get_default_merge():
    return pathlib.Path(get_profile_path(), "merge")


def get_default_current():
    return pathlib.Path(get_profile_path(), ".data")
