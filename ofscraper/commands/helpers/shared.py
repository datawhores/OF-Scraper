import ofscraper.utils.args.read as read_args


def run_action_bool():
    return len(read_args.retriveArgs().action) > 0



def run_metadata_bool():
    return read_args.retriveArgs().metadata