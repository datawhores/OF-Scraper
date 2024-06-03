import ofscraper.api.me as me
import ofscraper.utils.console as console
import ofscraper.utils.encoding as encoding
import ofscraper.utils.profiles.data as profile_data


def parse_user():
    profile = profile_data.get_my_info()
    name = encoding.encode_utf_16(profile["name"])
    username = profile["username"]
    return (name, username)


def get_id(refresh=True):
    profile = me.scrape_user(refresh=refresh)
    return profile["id"]


def print_user(name, username):
    console.get_shared_console().print(f"Welcome, {name} | {username}")
