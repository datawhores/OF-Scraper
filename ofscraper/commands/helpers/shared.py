import ofscraper.utils.args.read as read_args


def run_action_bool():
    return len(read_args.retriveArgs().action) > 0
