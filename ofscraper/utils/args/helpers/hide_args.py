def hide_check_mode(wrapper):
    for param in wrapper.params:
        if param.name in ["downloadthreads", "downloadsem", "downloadbars"]:
            param.hidden = True


def hide_manual_mode(wrapper):
    hide_check_mode(wrapper)


def hide_metadata_mode(wrapper):
    bad_args = ["download_limit", "no_auto_resume", "key_mode", "size_min", "size_max"]
    for param in wrapper.params:
        if param.name in bad_args:
            param.hidden = True
