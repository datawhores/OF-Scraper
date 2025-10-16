def set_download_type_flag(ctx, param, value):
    # 'value' will be True if --protected-only is used,
    # False if --normal-only is used, and None otherwise.
    if value is None:
        return None
    return "protected" if value else "normal"