from rich.console import Group

import ofscraper.utils.settings as settings
from ofscraper.utils.live.panel import Blue_Panel
from ofscraper.utils.live.progress import (
    activity_counter,
    activity_desc,
    api_job_progress,
    api_overall_progress,
    download_job_progress,
    download_overall_progress,
    like_overall_progress,
    userlist_job_progress,
    userlist_overall_progress,
    metadata_overall_progress,
)

# activity group
activity_desc_counter_group = Group(
    Blue_Panel(
        Group(activity_desc, activity_counter, fit=True), title="Activity Progress"
    )
)
activity_desc_group = Group(
    Blue_Panel(Group(activity_desc, fit=True), title="Activity Progress")
)


activity_counter_group = Group(
    Blue_Panel(Group(activity_counter, fit=True), title="Activity Progress")
)

# user
userlist_group = Group(
    activity_desc_counter_group,
    Blue_Panel(Group(userlist_overall_progress, userlist_job_progress)),
)


# like
like_progress_group = Group(
    activity_desc_counter_group, Blue_Panel(like_overall_progress)
)
# activity
api_progress_group = Group(
    activity_desc_counter_group,
    Blue_Panel(api_overall_progress, title="API Progress"),
    Blue_Panel(api_job_progress, title="API Messages"),
)


# download

download_overall_panel = Blue_Panel(
    download_overall_progress, style="bold deep_sky_blue2"
)
single_panel = Blue_Panel(download_job_progress, style="bold deep_sky_blue2")
download_progress_group = None


def get_download_group():
    global download_progress_group
    if not download_progress_group:
        download_progress_group = (
            Group(
                activity_desc_counter_group,
                download_overall_panel,
                single_panel,
                fit=True,
            )
            if settings.get_settings().download_bars
            else Group(activity_desc_counter_group, download_overall_panel, fit=True)
        )
    return download_progress_group


download_overall_progress_group = Group(
    activity_desc_counter_group, download_overall_panel, fit=True
)


# metadata
metadata_overall_panel = Blue_Panel(
    metadata_overall_progress, style="bold deep_sky_blue2"
)
metadata_group = Group(activity_desc_counter_group, metadata_overall_panel, fit=True)
