import ofscraper.utils.args.accessors.read as read_args


def is_trace():
    args = read_args.retriveArgs()
    return args.discord == "TRACE" or args.logs == "TRACE" or args.output == "TRACE"
