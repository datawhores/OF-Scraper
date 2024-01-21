import ofscraper.utils.args.globals as global_args
import ofscraper.utils.args.parse as parse_args


def retriveArgs():
    return global_args.args or parse_args.parse_args()
