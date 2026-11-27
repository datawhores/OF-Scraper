from ofscraper.scripts.after_action_script import run_after_action_script


def after_download_action_script(username, media, posts=None, action=None):
    run_after_action_script(
        username,
        media,
        posts=posts,
        action=action,
        default_action="download",
        label="download",
        level_key="AFTER_DOWNLOAD_ACTION_SCRIPT_SUBPROCESS_LEVEL",
    )
