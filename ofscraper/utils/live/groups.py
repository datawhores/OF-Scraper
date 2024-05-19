from rich.console import Group
from rich.panel import Panel

import ofscraper.utils.settings as settings

from ofscraper.utils.live.progress import download_job_progress,download_overall_progress,multi_download_job_progress,activity_counter,activity_progress,userlist_job_progress,userlist_overall_progress,like_overall_progress,api_job_progress,api_overall_progress
import ofscraper.utils.console as console


                                                    #activity group
activity_group=Group(Panel(Group(activity_progress,activity_counter,fit=True),title="Activity Progress", style="bold blue"))



#user
userlist_group=Group(activity_group,Panel(Group(userlist_overall_progress,userlist_job_progress)))


#like
like_progress_group=Panel(Group(activity_group,like_overall_progress))
#activity
api_progress_group = Group(activity_group,Panel(api_overall_progress,title="API Progress", style="bold blue"),Panel(api_job_progress,title="API Messages", style="bold blue",height=console.get_shared_console().size[-1] - 19))

    
#download

overall_panel=Panel(download_overall_progress, style="bold blue")
multi_panel=Panel(multi_download_job_progress, style="bold blue")
single_panel=Panel(download_job_progress, style="bold blue")
download_progress_group=None
multi_download_progress_group=None
def get_download_group():
    global download_progress_group
    if not download_progress_group:
        download_progress_group = Group(activity_group,overall_panel,single_panel,fit=True ) if settings.get_download_bars() else Group(overall_panel,activity_group,fit=True )
    return download_progress_group

def get_multi_download_progress_group():
    global multi_download_progress_group
    if not multi_download_progress_group:
        multi_download_progress_group= Group(activity_group,overall_panel, multi_panel,fit=True) if settings.get_download_bars() else Group(activity_group,overall_panel,fit=True)
    return multi_download_progress_group

