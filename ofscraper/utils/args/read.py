import sys

import ofscraper.utils.args.globals as global_args
import ofscraper.utils.args.parse as parse_args


def retriveArgs():
    try:
        return global_args.args or parse_args.parse_args()
    except SystemExit as E:
        print(f"Passed Args {sys.argv[1:]}")
        raise E
