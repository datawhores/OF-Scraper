import inspect
import json
import pathlib
import platform
import re
import string

import arrow
from pathvalidate import validate_filename, validate_filepath
from prompt_toolkit.validation import ValidationError, Validator

import ofscraper.classes.placeholder as placeholders
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.paths.check as paths_check
import ofscraper.utils.profiles.data as profiles_data
import ofscraper.utils.profiles.tools as profiles_tools


class MultiValidator(Validator):
    """:Runs Multiple Validators Since Inquirerpy does seem to support this functionality natively

    Args:
        *args:List of validator objects

    """

    def __init__(self, *args):
        self.inputs = args

    def validate(self, document) -> None:
        for input in self.inputs:
            try:
                if isinstance(input, Validator):
                    input.validate(document)
                else:
                    if input(document.text) is False:
                        raise Exception()
            except ValidationError as E:
                raise E
            except Exception as E:
                raise ValidationError(
                    message=E,
                    cursor_position=document.cursor_position,
                )


def validatorCallableHelper(funct, message, move_cursor_to_end=False):
    return Validator.from_callable(
        funct,
        inspect.cleandoc(message).strip().replace("\n", " "),
        move_cursor_to_end=move_cursor_to_end,
    )


def currentProfilesValidator():
    def callable(x):
        x = profiles_tools.profile_name_fixer(x)
        return x not in set(profiles_data.get_profile_names())

    return validatorCallableHelper(
        callable, "You can not change name to a current profile name"
    )


def currentProfilesCreationValidator():
    def callable(x):
        x = profiles_tools.profile_name_fixer(x)
        return x not in set(profiles_data.get_profile_names())

    return validatorCallableHelper(callable, "This Profile already exists")


def currentProfileDeleteValidator():
    def callable(x):
        return (
            profiles_tools.profile_name_fixer(x) != profiles_data.get_active_profile()
        )

    return validatorCallableHelper(callable, "You can not delete the active profile")


def emptyListValidator():
    def callable(x):
        return len(x) > 0

    return validatorCallableHelper(callable, "You must select at least one")


def cleanTextInput(x):
    return x.strip()


def jsonValidator():
    def callable(x):
        try:
            json.loads(x)
            return True
        except:
            return

    return validatorCallableHelper(
        callable,
        "Invalid JSON syntax",
        move_cursor_to_end=True,
    )


def jsonloader(x):
    try:
        return json.loads(x)
    except TypeError:
        return None
    except json.JSONDecodeError:
        return None
    except Exception as E:
        raise E


def namevalitator():
    def callable(x):
        validchars = re.search("[a-zA-Z0-9_]*", x)
        return validchars is not None and len(x) == len(validchars.group(0))

    return validatorCallableHelper(
        callable,
        "ONLY letters, numbers, and underscores are allowed",
        move_cursor_to_end=True,
    )


def dirformatvalidator():
    def callable(x):
        try:
            testplaceholders = list(
                filter(
                    lambda x: x is not None, [v[1] for v in string.Formatter().parse(x)]
                )
            )
            validplaceholders = placeholders.all_placeholders()
            if (
                len(
                    list(
                        filter(
                            lambda x: x not in validplaceholders
                            or not x.find("custom"),
                            testplaceholders,
                        )
                    )
                )
                > 0
            ):
                return
            result = {}

            for d in list(map(lambda x: {x: "placeholder"}, placeholders)):
                result.update(d)
            validate_filepath(
                str(pathlib.Path(x.format(**result))), platform=platform.system()
            )

            return True
        except:
            return

    return validatorCallableHelper(
        callable,
        inspect.cleandoc(
            """
Improper syntax or invalid placeholder
"""
        ).strip(),
        move_cursor_to_end=True,
    )


def fileformatvalidator():
    def callable(x):
        try:
            placeholders = list(
                filter(
                    lambda x: x is not None, [v[1] for v in string.Formatter().parse(x)]
                )
            )
            validplaceholders = set(
                [
                    "date",
                    "responsetype",
                    "mediatype",
                    "model_id",
                    "first_letter",
                    "sitename",
                    "model_username",
                    "post_id",
                    "filename",
                    "value",
                    "text",
                    "ext",
                ]
            )

            if (
                len(list(filter(lambda x: x not in validplaceholders, placeholders)))
                > 0
            ):
                return
            result = {}

            for d in list(map(lambda x: {x: "placeholder"}, placeholders)):
                result.update(d)
            validate_filename(x.format(**result), platform=platform.system())

            return True
        except:
            return

    return validatorCallableHelper(
        callable,
        inspect.cleandoc(
            """
Improper syntax or invalid placeholder
"""
        ).strip(),
        move_cursor_to_end=True,
    )


def dateplaceholdervalidator():
    def callable(x):
        try:
            if arrow.utcnow().format(x) == x:
                return
            return True
        except:
            return

    return validatorCallableHelper(
        callable,
        """Date Format is invalid -> https://arrow.readthedocs.io/en/latest/guide.html#supported-tokens""",
    )


def datevalidator():
    def callable(x):
        try:
            return arrow.get(x or 0)
        except:
            return

    return validatorCallableHelper(
        callable,
        """
        Date is invalid -> https://arrow.readthedocs.io/en/latest/guide.html#supported-tokens""",
    )


def ffmpegpathvalidator():
    def callable(x):
        return paths_check.ffmpegpathcheck(x)

    return validatorCallableHelper(
        callable,
        inspect.cleandoc(
            """
Path to ffmpeg is not valid filepath or does not exists
"""
        ).strip(),
        move_cursor_to_end=True,
    )


def ffmpegexecutevalidator():
    def callable(x):
        return paths_check.ffmpegexecutecheck(x)

    return validatorCallableHelper(
        callable,
        inspect.cleandoc(
            """
Path is valid but the given path could not be verified to be ffmpeg
"""
        ).strip(),
        move_cursor_to_end=True,
    )


def like_area_validator_posts():
    def callable(x):
        args = read_args.retriveArgs()
        if "like" not in args.action and "unlike" not in args.action:
            return True
        elif len(args.like_area) > 0:
            return True
        elif "All" in args.like_area:
            return True
        elif (
            "Timeline" not in x + list(args.posts)
            and "Pinned" not in x + list(args.posts)
            and "Archived" not in x + list(args.posts)
            and "Labels" not in x + list(args.posts)
            and "Streams" not in x + list(args.posts)
        ):
            return
        return True

    return validatorCallableHelper(
        callable,
        inspect.cleandoc(
            """
You must select at least one of the following Timeline,Pinned, Archived
When like/unlike is action is on
"""
        ).strip(),
        move_cursor_to_end=True,
    )


def metadatavalidator():
    def callable(x):
        try:
            placeholders = list(
                filter(
                    lambda x: x is not None, [v[1] for v in string.Formatter().parse(x)]
                )
            )
            validplaceholders = set(
                [
                    "sitename",
                    "first_letter",
                    "model_username",
                    "model_id",
                    "configpath",
                    "profile",
                ]
            )
            if (
                len(list(filter(lambda x: x not in validplaceholders, placeholders)))
                > 0
            ):
                return
            result = {}

            for d in list(map(lambda x: {x: "placeholder"}, placeholders)):
                result.update(d)
            validate_filepath(
                str(pathlib.Path(x.format(**result))), platform=platform.system()
            )

            return True
        except:
            return

    return validatorCallableHelper(
        callable,
        inspect.cleandoc(
            """
Improper syntax or invalid placeholder
"""
        ).strip(),
        move_cursor_to_end=True,
    )


def DiscordValidator():
    def callable(x):
        if len(x) == 0:
            return True
        return (
            re.search("https://discord.com/api/webhooks/[0-9]*/[0-9a-z]*", x)
            is not None
        )

    return validatorCallableHelper(
        callable,
        inspect.cleandoc(
            """
must be discord webhook -> example: https://discord.com/api/webhooks/{numeric}/{alphanumeric}
    """
        ).strip(),
    )
