import argparse
import pathlib
import re

import arrow


def check_strhelper(x):
    temp = None
    if isinstance(x, list):
        temp = x
    elif isinstance(x, str):
        temp = re.split(",| ", x)
    return temp


def check_filehelper(x):
    if isinstance(x, str) and pathlib.Path(x).exists():
        with open(x, "r") as _:
            return _.readlines()
    return []


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
            "Labels+",
            "Labels*",
        ]
    )
    if isinstance(x, str):
        x = re.split(",| ", x)
        x = list(map(lambda x: re.sub("[^a-zA-Z-\*\+]", "", str.title(x)), x))
    if len(list(filter(lambda y: y not in choices and y[1:] not in choices, x))) > 0:
        raise argparse.ArgumentTypeError(
            "error: argument -o/--posts: invalid choice: (choose from 'highlights', 'all', 'archived', 'messages', 'timeline', 'pinned', 'stories', 'purchased','profile','labels')"
        )
    return x


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
            "Labels+",
            "Labels*",
        ]
    )
    if isinstance(x, str):
        x = re.split(",| ", x)
        x = list(map(lambda x: re.sub("[^a-zA-Z\*\+]", "", str.title(x)), x))
    if len(list(filter(lambda y: y not in choices and y[1:] not in choices), x)) > 0:
        raise argparse.ArgumentTypeError(
            "error: argument -da/--download-area: invalid choice: (choose from 'highlights', 'all', 'archived', 'messages', 'timeline', 'pinned', 'stories', 'purchased','profile','labels')"
        )
    seen = set()
    return [post for post in x if post not in seen and not seen.add(post)]


def like_helper(x):
    choices = set(["All", "Archived", "Timeline", "Pinned", "Labels"])
    if isinstance(x, str):
        x = re.split(",| ", x)
        x = list(map(lambda x: re.sub("[^a-zA-Z-\*\+]", "", str.title(x)), x))
    if len(list(filter(lambda y: y not in choices and y[1:] not in choices, x))) > 0:
        raise argparse.ArgumentTypeError(
            "error: argument -la/--like-area: invalid choice: (choose from 'all', 'archived', 'timeline', 'pinned','labels')"
        )
    seen = set()
    return [post for post in x if post not in seen and not seen.add(post)]


def post_check_area(x):
    choices = set(["All", "Archived", "Timeline", "Pinned", "Labels"])
    if isinstance(x, str):
        x = re.split(",| ", x)
        x = list(map(lambda x: re.sub("[^a-zA-Z-\*\+]", "", str.title(x)), x))
    if len(list(filter(lambda y: y not in choices and y[1:] not in choices, x))) > 0:
        raise argparse.ArgumentTypeError(
            "error: argument -la/--like-area: invalid choice: (choose from 'all', 'archived', 'timeline', 'pinned','labels')"
        )
    seen = set()
    return [post for post in x if post not in seen and not seen.add(post)]


def mediatype_helper(x):
    choices = set(["Videos", "Audios", "Images", "Text"])
    if isinstance(x, str):
        x = re.split(",| ", x)
        x = list(map(lambda x: x.capitalize(), x))
    if len(list(filter(lambda y: y not in choices, x))) > 0:
        raise argparse.ArgumentTypeError(
            "error: argument -o/--mediatype: invalid choice: (choose from 'images','audios','videos','text')"
        )
    seen = set()
    return [post for post in x if post not in seen and not seen.add(post)]


def action_helper(x):
    select = re.split(",| ", x)
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
                    lambda x: x in set(["like", "unlike", "download"]),
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
        temp = re.split(",| ", x)

    return list(map(lambda x: x.lower() if not x == "ALL" else x, temp))


def label_helper(x):
    temp = None
    if isinstance(x, list):
        temp = x
    elif isinstance(x, str):
        temp = re.split(",| ", x)
    return list(map(lambda x: x.lower(), temp))


def arrow_helper(x):
    try:
        t = arrow.get(x)
    except arrow.parser.ParserError:
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
