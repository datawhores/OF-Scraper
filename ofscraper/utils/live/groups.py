from rich.console import Group
from rich.panel import Panel

import ofscraper.utils.settings as settings

from ofscraper.utils.live.progress import download_job_progress,download_overall_progress,multi_download_job_progress,activity_counter,activity_progress,userlist_job_progress,userlist_overall_progress,like_overall_progress

                                                    #activity group
activity_group=Group(Panel(Group(activity_progress,activity_counter,fit=True)))

#download

overall_panel=Panel(download_overall_progress)
multi_panel=Panel(multi_download_job_progress)
single_panel=Panel(download_job_progress)
download_progress_group=None
multi_download_progress_group=None


#user
userlist_group=Group(Panel(Group(userlist_overall_progress,userlist_job_progress)))


#like
like_progress_group=Panel(Group(like_overall_progress,activity_group))

def get_download_group():
    global download_progress_group
    if not download_progress_group:
        download_progress_group = Group(overall_panel,activity_group,single_panel,fit=True ) if settings.get_download_bars() else Group(overall_panel,activity_group,fit=True ) 
    return download_progress_group

def get_multi_download_progress_group():
    global multi_download_progress_group
    if not multi_download_progress_group:
        multi_download_progress_group= Group(overall_panel,activity_group, multi_panel,fit=True) if settings.get_download_bars() else Group(overall_panel,activity_group,fit=True)
    return multi_download_progress_group


