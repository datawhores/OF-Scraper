

def set_search_strategy_flag(ctx, param, value):
    # 'value' is True for --individual, False for --list, None by default.
    if value is True:
        return "individual"
    elif value is False:
        return "list"
    return