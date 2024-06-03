import ofscraper.utils.args.read as read_args

def low_output():
     return read_args.retriveArgs().output in {"OFF", "LOW", "PROMPT"} or read_args.retriveArgs().no_rich
