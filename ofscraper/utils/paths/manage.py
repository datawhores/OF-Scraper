import ofscraper.utils.paths.common as common_paths


def make_folders():
    common_paths.get_config_folder()
    create_profile_path()


def create_profile_path(name=None):
    out = common_paths.get_profile_path(name)
    out.mkdir(exist_ok=True, parents=True)
    return out
