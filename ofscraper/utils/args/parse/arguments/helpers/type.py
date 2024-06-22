import argparse
import pathlib
import re
import arrow


def check_modes_strhelper(x):
    temp = string_split_helper(x)
    return temp


def check_modes_filehelper(x):
    if isinstance(x, str) and pathlib.Path(x).exists():
        with open(x, "r") as _:
            return _.readlines()
    return []


def post_type_helper(x):
    choices = set(
        [
            "Highlights",
            "All",
            "Archived",
            "Messages",
            "Timeline",
            "Pinned",
            "Streams",
            "Stories",
            "Purchased",
            "Profile",
            "Labels",
            "Labels+",
            "Labels*",
        ]
    )
    x = string_split_helper_filtered(x)
    if len(list(filter((lambda y: y not in choices and y[1:] not in choices), x))) > 0:
        raise argparse.ArgumentTypeError(
            "error: argument -o/--posts: invalid choice: (choose from 'highlights', 'all', 'archived', 'messages', 'timeline', 'pinned', 'stories', 'purchased','profile','labels')"
        )
    return final_output_dupe_helper(x)






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
            "Streams",
            "Labels",
            "Labels+",
            "Labels*",
        ]
    )
    x = string_split_helper_filtered(x)
    if len(list(filter((lambda y: y not in choices and y[1:] not in choices), x))) > 0:
        raise argparse.ArgumentTypeError(
            "error: argument -da/--download-area: invalid choice: (choose from 'highlights', 'all', 'archived', 'messages', 'timeline', 'pinned', 'stories', 'purchased','profile','labels')"
        )
    return final_output_dupe_helper(x)


def like_helper(x):
    choices = set(["All", "Archived", "Timeline", "Pinned", "Labels","Streams"])
    x = string_split_helper_filtered(x)
    if len(list(filter((lambda y: y not in choices and y[1:] not in choices), x))) > 0:
        raise argparse.ArgumentTypeError(
            "error: argument -la/--like-area: invalid choice: (choose from 'all', 'archived', 'timeline', 'pinned','labels')"
        )
    return final_output_dupe_helper(x)


def post_check_area_helper(x):
    choices = set(["All", "Archived", "Timeline", "Pinned", "Labels","Streams"])
    x = string_split_helper_filtered(x)
    if len(list(filter((lambda y: y not in choices and y[1:] not in choices), x))) > 0:
        raise argparse.ArgumentTypeError(
            "error: argument -la/--like-area: invalid choice: (choose from 'all', 'archived', 'timeline', 'pinned','labels')"
        )
    return final_output_dupe_helper(x)


def mediatype_helper(x):
    choices = set(["Videos", "Audios", "Images", "Text"])
    x = string_split_helper(x)
    if len(filter_helper(choices,x)) > 0:
        raise argparse.ArgumentTypeError(
            "error: argument -o/--mediatype: invalid choice: (choose from 'images','audios','videos','text')"
        )
    return final_output_dupe_helper(x)


def action_helper(x):
    select = string_split_helper(x)
    select = list(map(lambda x: x.lower(), select))
    select= final_output_dupe_helper(select)
    if "like" in select and "unlike" in select:
        raise argparse.ArgumentTypeError(
            "You can not select like and unlike at the same time"
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

def post_id_helper(data):
    x = string_split_helper(data)
    out=[]
    for ele in x:
        match = re.findall(r"\d+", ele)
        out.append(match[-1]) if bool(match) else None
    return out






def username_helper(data):
    temp =string_split_helper(data)
    temp = list(filter(lambda x: len(x) > 0, temp))
    final=list(map(lambda y: y.lower() if not y == "ALL" else y, temp))
    return final_output_dupe_helper(final)


def label_helper(x):
    temp = string_split_helper_filtered(x)
    temp=list(map(lambda x: x.lower(), temp))
    return final_output_dupe_helper(temp)


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
    if not t:
        return None
    return t if t > arrow.get("2006.6.30") else arrow.get(0)


def filter_helper(choices,selections):
    return list(filter((lambda y: y not in choices and y[1:] not in choices and y[:1] not in choices), selections))

def final_output_dupe_helper(x):
    seen = set()
    return [post for post in x if post not in seen and not seen.add(post)]

def string_split_helper(x):
    if isinstance(x, str):
        x = re.split(",| ", x)   
    return x

def string_split_helper_filtered(x):
    x=string_split_helper(x)
    x = list(map(lambda x: re.sub(r"[^a-zA-Z-\*\+]", "", str.title(x)), x))
    return x