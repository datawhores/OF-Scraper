import argparse
import pathlib
import re

import arrow
from humanfriendly import parse_size

from ofscraper.__version__ import __version__


def check_strhelper(x):
    temp = None
    if isinstance(x, list):
        temp = x
    elif isinstance(x, str):
        temp = x.split(",")
    return temp


def check_filehelper(x):
    if isinstance(x, str) and pathlib.Path(x).exists():
        with open(x, "r") as _:
            return _.readlines()


def posttype_helper(x):
    choices = set(
        [
            "Highlights",
            "All",
            "Archived",
            "Messages",
            "Timeline",
            "Pinned",
            "Stories",
            "Purchased",
            "Profile",
            "Labels",
        ]
    )
    if isinstance(x, str):
        words = x.split(",")
        words = list(map(lambda x: re.sub("[^a-zA-Z-]", "", str.title(x)), words))
    if (
        len(list(filter(lambda y: y not in choices and y[1:] not in choices, words)))
        > 0
    ):
        raise argparse.ArgumentTypeError(
            "error: argument -o/--posts: invalid choice: (choose from 'highlights', 'all', 'archived', 'messages', 'timeline', 'pinned', 'stories', 'purchased','profile','labels')"
        )
    return words


def download_helper(x):
    choices = set(
        [
            "Highlights",
            "All",
            "Archived",
            "Messages",
            "Timeline",
            "Pinned",
            "Stories",
            "Purchased",
            "Profile",
            "Labels",
        ]
    )
    if isinstance(x, str):
        words = x.split(",")
        words = list(map(lambda x: re.sub("[^a-zA-Z-]", "", str.title(x)), words))
    if (
        len(list(filter(lambda y: y not in choices and y[1:] not in choices), words))
        > 0
    ):
        raise argparse.ArgumentTypeError(
            "error: argument -da/--download-area: invalid choice: (choose from 'highlights', 'all', 'archived', 'messages', 'timeline', 'pinned', 'stories', 'purchased','profile','labels')"
        )
    return words


def like_helper(x):
    choices = set(["All", "Archived", "Timeline", "Pinned", "Labels"])
    if isinstance(x, str):
        words = x.split(",")
        words = list(map(lambda x: re.sub("[^a-zA-Z-]", "", str.title(x)), words))
    if (
        len(list(filter(lambda y: y not in choices and y[1:] not in choices, words)))
        > 0
    ):
        raise argparse.ArgumentTypeError(
            "error: argument -la/--like-area: invalid choice: (choose from 'all', 'archived', 'timeline', 'pinned','labels')"
        )
    return words


def mediatype_helper(x):
    choices = set(["Videos", "Audio", "Images"])
    if isinstance(x, str):
        x = x.split(",")
        x = list(map(lambda x: x.capitalize(), x))
    if len(list(filter(lambda y: y not in choices, x))) > 0:
        raise argparse.ArgumentTypeError(
            "error: argument -o/--mediatype: invalid choice: (choose from 'images','audio','videos')"
        )
    return x


def action_helper(x):
    select = x.split(",")
    select = list(map(lambda x: x.lower(), select))
    if "like" in select and "unlike" in select:
        raise argparse.ArgumentTypeError(
            "You can not select like and unlike at the same time"
        )
    elif "download" in select and "metadata" in select:
        raise argparse.ArgumentTypeError(
            "You can not select metadata and download at the same time"
        )

    elif (
        len(
            list(
                filter(
                    lambda x: x in set(["like", "unlike", "download", "metadata"]),
                    select,
                )
            )
        )
        == 0
    ):
        raise argparse.ArgumentTypeError(
            "You must select [like or unlike] and/or download for action"
        )
    return select


def changeargs(newargs):
    global args
    args = newargs


def username_helper(x):
    temp = None
    if isinstance(x, list):
        temp = x
    elif isinstance(x, str):
        temp = x.split(",")

    return list(map(lambda x: x.lower() if not x == "ALL" else x, temp))


def label_helper(x):
    temp = None
    if isinstance(x, list):
        temp = x
    elif isinstance(x, str):
        temp = x.split(",")
    return list(map(lambda x: x.lower(), temp))


def arrow_helper(x):
    try:
        t = arrow.get(x)
    except arrow.parser.ParserError as E:
        try:
            x = re.sub("\\byear\\b", "years", x)
            x = re.sub("\\bday\\b", "days", x)
            x = re.sub("\\bmonth\\b", "months", x)
            x = re.sub("\\bweek\\b", "weeks", x)
            arw = arrow.utcnow()
            t = arw.dehumanize(x)
        except ValueError as E:
            raise E
    return t if t > arrow.get("2006.6.30") else 0
