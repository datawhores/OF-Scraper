from rich.console import Console

import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.encoding as encoding


def parse_user(profile):
    name = encoding.encode_utf_16(profile["name"])
    username = profile["username"]

    return (name, username)


def print_user(name, username):
    with stdout.lowstdout():
        Console().print(f"Welcome, {name} | {username}")
