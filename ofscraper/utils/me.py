from rich.console import Console

import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.encoding as encoding
import ofscraper.api.me as me


def parse_user():
    profile = me.scrape_user()

    name = encoding.encode_utf_16(profile["name"])
    username = profile["username"]
    return (name, username)

def get_id():
    profile = me.scrape_user()
    return profile["id"]

def print_user(name, username):
    with stdout.lowstdout():
        Console().print(f"Welcome, {name} | {username}")
