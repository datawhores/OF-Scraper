import ofscraper.data.api.me as me
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.console as console
import ofscraper.utils.encoding as encoding
import ofscraper.utils.profiles.data as profile_data


def parse_user():
    if read_args.retriveArgs().anon:
        return ("anon", "anon")
    profile = profile_data.get_my_info()
    name = encoding.encode_utf_16(profile["name"])
    username = profile["username"]
    return (name, username)


def get_id():
    profile = me.scrape_user()
    return profile["id"]


def print_user(name, username):
    console.get_shared_console().print(f"Welcome, {name} | {username}")
