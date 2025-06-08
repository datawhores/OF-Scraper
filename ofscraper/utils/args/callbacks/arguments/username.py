

def set_search_strategy_flag(ctx, param, value):
    # 'value' is True for --individual, False for --list, None by default.
    if value is True:
        return "individual"
    # For both --list (value=False) and the default case (value=None),
    # we'll return "list".
    return "list"