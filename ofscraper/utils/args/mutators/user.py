import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args


def resetUserFilters():
    args = read_args.retriveArgs()
    args.user_list = []
    args.black_list = []
    args.renewal = None
    args.sub_status = None
    args.last_seen = None
    args.last_seen_after = None
    args.last_seen_before = None
    args.promo = None
    args.all_promo = None
    args.free_trial = None
    args.regular_price = None
    args.renewal_price = None
    args.current_price = None
    args.promo_price = None
    args.sort = "name"
    args.desc = False
    return args


def set_users_arg(input_):
    args = read_args.retriveArgs()
    args.usernames = input_
    write_args.setArgs(args)
