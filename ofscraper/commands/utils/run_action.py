import ofscraper.utils.args.accessors.read as read_args


def run_action_bool():
    return len(read_args.retriveArgs().action) > 0



