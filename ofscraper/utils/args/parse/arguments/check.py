# checkmode  args
import itertools
import cloup as click

import ofscraper.utils.args.parse.arguments.helpers.type as type
check_areas=click.option(
        "-ca",
        "--check-area",
         "--post",
        "--post",
        "check_area",
        help="Select areas to check (multiple allowed, separated by spaces)",
        default=["Timeline", "Pinned", "Archived","Streams"],
        type=type.post_check_area_helper,
        callback=lambda ctx, param, value: (
        list(set(itertools.chain.from_iterable(value))) if value else []
        ),
        multiple=True,
)


url_option=click.option(
            "-u",
            "--url",
            help="Scan posts via space or comma seperated list of urls",
            default=None,
            multiple=True,
            type=type.check_modes_strhelper,
            callback=lambda ctx, param, value: (
                list(set(itertools.chain.from_iterable(value))) if value else []
            ),
        )
file_option=click.option(
            "-f",
            "--file",
            help="Scan posts via a file with line-separated URL(s)",
            default=None,
            type=type.check_modes_filehelper,
            multiple=True,
            callback=lambda ctx, param, value: (
                list(set(itertools.chain.from_iterable(value))) if value else []
            ),
        )


file_username_option=click.option(
            "-f",
            "--file",
            help="Scan posts via a file with line-separated URL(s)",
            default=None,
            type=type.check_modes_filehelper,
            multiple=True,
            callback=lambda ctx, param, value: (
                list(set(itertools.chain.from_iterable(value))) if value else []
            ),
        )
user_option=click.option(
            "-u",
            "--usernames",
            "--username",
            "check_usernames",
            help="Scan stories/highlights via username(s)",
            default=None,
            multiple=True,
            type=type.check_modes_strhelper,
            callback=lambda ctx, param, value: (
                list(set(itertools.chain.from_iterable(value))) if value else []
            ),
)
force=click.option(
        "-fo",
        "--force",
        help="Force retrieval of new posts info from API",
        is_flag=True,
        default=False,
)
url_group=click.constraints.require_one(
      url_option,
      file_option
)

username_group=click.constraints.require_one(
      user_option,
      file_username_option
)
