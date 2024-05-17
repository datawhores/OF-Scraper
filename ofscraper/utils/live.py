import contextlib
from rich import abc
from rich.console import Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
        MofNCompleteColumn,

)
from rich.style import Style
from rich.table import Column

import ofscraper.utils.console as console_
import ofscraper.utils.constants as constants
from ofscraper.classes.multiprocessprogress import MultiprocessProgress as MultiProgress
import ofscraper.utils.settings as settings


set_up=False


#main context and switches
@contextlib.contextmanager
def live_progress_context(stop=False):
    global set_up
    if not set_up:
        set_all_up_progress()
        set_up=True
    if not live.is_started:
        live.start()
    yield
    if stop:
        remove_task()
        live.stop()
def remove_task():
    global activity_task
    global user_first_task
    global activity_counter_task
    if activity_task:
        activity_progress.remove_task(
            activity_task
     )
    if user_first_task:
        activity_counter.remove_task(
            user_first_task
     )
    if activity_counter_task:
            activity_counter.remove_task(
            activity_counter_task
     )



@contextlib.contextmanager
def setup_download_progress_live(multi=False,stop=False):
    global download_job_progress
    global download_overall_progress
    global download_progress_group
    global multi_download_progress_group
    global live
    with live_progress_context(stop=stop):
        if multi:
            live.update(multi_download_progress_group,refresh=True)
        else:
            live.update(download_progress_group,refresh=True)
        yield
@contextlib.contextmanager

def setup_api_split_progress_live(stop=False):
    global timeline_layout
    global pinned_layout
    global archived_layout
    global labelled_layout
    global messages_layout
    global paid_layout
    global stories_layout
    global highlights_layout
    global live
    global api_progress_group
    global username_task
    global activity_group
    global api_overall_progress
    with live_progress_context(stop=stop):
        layout = Layout(name="parent")
        layout.visible = constants.getattr("API_DISPLAY")

        layout.split_column(Layout(name="upper", ratio=1), Layout(name="lower", ratio=1))
        layout["upper"].split_row(
            timeline_layout,
            pinned_layout,
            archived_layout,
            labelled_layout,
            Layout(name="OF-Scraper", size=0, ratio=0),
        ),
        layout["lower"].split_row(
            messages_layout,
            paid_layout,
            stories_layout,
            highlights_layout,
            Layout(name="OF-Scaper", size=0, ratio=0),
        )

        api_progress_group = Group(Panel(Group(api_overall_progress)),activity_group, layout)
        live.update(api_progress_group,refresh=True)
        yield


@contextlib.contextmanager
def setup_subscription_progress_live(stop=False):
    global live
    global userlist_job_progress
    global userlist_overall_progress
    global userlist_group
    with live_progress_context(stop=stop):
        live.update(userlist_group,refresh=True)
        yield


@contextlib.contextmanager
def setup_like_progress_live(stop=False):
    global live
    global like_progress_group
    with live_progress_context(stop=stop):
        live.update(like_progress_group,refresh=True)
        yield




def set_up_api_layout():
    global timeline_progress
    global pinned_progress
    global archived_progress
    global messages_progress
    global paid_progress
    global labelled_progress
    global highlights_progress
    global stories_progress
    global timeline_layout
    global pinned_layout
    global archived_layout
    global labelled_layout
    global messages_layout
    global paid_layout
    global stories_layout
    global highlights_layout

    timeline_layout = Layout(
        Panel(timeline_progress, title="Timeline Info"), name="timeline"
    )
    pinned_layout = Layout(Panel(pinned_progress, title="Pinned Info"), name="pinned")
    archived_layout = Layout(
        Panel(archived_progress, title="Archived Info"), name="archived"
    )
    labelled_layout = Layout(
        Panel(labelled_progress, title="Labelled Info"), name="labelled"
    )
    messages_layout = Layout(
        Panel(messages_progress, title="Messages Info"), name="messages"
    )
    paid_layout = Layout(Panel(paid_progress, title="Paid Info"), name="paid")
    stories_layout = Layout(
        Panel(stories_progress, title="Stories Info"), name="stories"
    )
    highlights_layout = Layout(
        Panel(highlights_progress, title="Highlights Info"), name="highlights"
    )

    timeline_layout.visible = False
    pinned_layout.visible = False
    archived_layout.visible = False
    labelled_layout.visible = False
    messages_layout.visible = False
    paid_layout.visible = False
    stories_layout.visible = False
    highlights_layout.visible = False



def set_up_api_progress():
    global timeline_progress
    global pinned_progress
    global api_overall_progress
    global archived_progress
    global messages_progress
    global paid_progress
    global labelled_progress
    global highlights_progress
    global stories_progress
    global username_task
    timeline_progress = Progress(
        "{task.description}", console=console_.get_temp_console()
    )
    pinned_progress = Progress(
        "{task.description}", console=console_.get_temp_console()
    )
    api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("{task.description}"),
        console=console_.get_temp_console(),
    )
    archived_progress = Progress(
        "{task.description}", console=console_.get_temp_console()
    )
    messages_progress = Progress(
        "{task.description}", console=console_.get_temp_console()
    )
    paid_progress = Progress("{task.description}", console=console_.get_temp_console())
    labelled_progress = Progress(
        "{task.description}", console=console_.get_temp_console()
    )
    highlights_progress = Progress(
        "{task.description}", console=console_.get_temp_console()
    )
    stories_progress = Progress(
        "{task.description}", console=console_.get_temp_console()
    )
    # tasks from progress
    username_task=None
def set_up_userlist_progress():
    global userlist_group
    global userlist_overall_progress
    global userlist_job_progress

    userlist_overall_progress=Progress(
                    SpinnerColumn(style=Style(color="blue")), TextColumn("{task.description}")
    )
    userlist_job_progress = Progress("{task.description}")
    userlist_group=Group(Panel(Group(userlist_overall_progress,userlist_job_progress)))

def set_up_shared_activity_progress():
    global activity_progress
    global activity_counter
    global activity_group
    global activity_task
    global activity_counter_task
    global user_first_task


    activity_progress=Progress(
    TextColumn("{task.description}"),
    TimeElapsedColumn(),
    )
    activity_counter=Progress(
    TextColumn("{task.description}"),
    BarColumn(table_column=Column(ratio=3),bar_width=100),
    MofNCompleteColumn())

    activity_group=Group(Panel(Group(activity_progress,activity_counter,fit=True)))

    activity_task=activity_progress.add_task(
            description='Running OF-Scraper'
     )
    activity_counter_task=activity_counter.add_task(
            description='Overall script progress',
     )
    user_first_task=None




def set_up_like_progress():
    global like_overall_progress
    global like_progress_group
    global activity_group
    like_overall_progress=Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("{task.description}"),
        BarColumn(table_column=Column(ratio=2)),
        MofNCompleteColumn(),
    )
    like_progress_group=Panel(Group(like_overall_progress,activity_group))


def set_up_download_progress():
    global download_job_progress
    global download_overall_progress
    global download_progress_group
    global multi_download_progress_group
    global multi_download_job_progress
    global activity_group
    download_overall_progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
    )
    multi_download_job_progress = MultiProgress(
                TextColumn("{task.description}", table_column=Column(ratio=2)),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                TransferSpeedColumn(),
                DownloadColumn(),
    )
    download_job_progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console_.get_temp_console(),
    )
    height=max(15, console_.get_shared_console().size[-1] - 2)
    enabled=settings.get_download_bars()

    overall_panel=Panel(download_overall_progress)
    multi_panel=Panel(multi_download_job_progress,height=height)
    single_panel=Panel(download_job_progress,height=height)

    download_progress_group = Group(overall_panel,activity_group,single_panel,fit=True ) if enabled else Group(overall_panel,activity_group,fit=True )
    multi_download_progress_group= Group(overall_panel,activity_group, multi_panel,fit=True) if enabled else Group(overall_panel,activity_group,fit=True)




def set_all_up_progress():
    global live
    live=Live( transient=False,refresh_per_second=4,console=console_.get_shared_console())
    set_up_shared_activity_progress()
    set_up_api_progress()
    set_up_api_layout()
    set_up_like_progress()
    set_up_download_progress()
    set_up_userlist_progress()



#api progress

def setup_all_paid_live():
    global all_paid_progress
    global api_overall_progress
    all_paid_progress = Progress("{task.description}")
    api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("{task.description}"),
        console=console_.get_temp_console(quiet=False),
    )
    progress_group = Group(api_overall_progress, Panel(Group(all_paid_progress)))

    return Live(
        progress_group,
        refresh_per_second=5,
        console=console_.get_shared_console(),
        transient=True,
    )
def set_up_api_timeline():
    global api_overall_progress
    global timeline_progress
    api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("Getting timeline posts...\n{task.description}"),
    )
    timeline_progress = Progress("{task.description}")
    progress_group = Group(api_overall_progress, Panel(Group(timeline_progress)))
    return Live(
        progress_group,
        refresh_per_second=5,
        console=console_.get_shared_console(),
        transient=True,
    )


def set_up_api_pinned():
    global api_overall_progress
    global pinned_progress
    api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("Getting pinned posts...\n{task.description}"),
        console=console_.get_temp_console(),
    )
    pinned_progress = Progress("{task.description}")
    progress_group = Group(api_overall_progress, Panel(Group(pinned_progress)))
    return Live(
        progress_group,
        refresh_per_second=5,
        console=console_.get_shared_console(),
        transient=True,
    )


def set_up_api_paid():
    global api_overall_progress
    global paid_progress
    api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("Getting paid posts...\n{task.description}"),
        console=console_.get_temp_console(),
    )
    paid_progress = Progress("{task.description}")
    progress_group = Group(api_overall_progress, Panel(Group(paid_progress)))
    return Live(
        progress_group,
        refresh_per_second=5,
        console=console_.get_shared_console(),
        transient=True,
    )


def set_up_api_messages():
    global api_overall_progress
    global messages_progress
    api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("Getting messages...\n{task.description}"),
        console=console_.get_temp_console(),
    )
    messages_progress = Progress("{task.description}")
    progress_group = Group(api_overall_progress, Panel(Group(messages_progress)))
    return Live(
        progress_group,
        refresh_per_second=5,
        console=console_.get_shared_console(),
        transient=True,
    )


def set_up_api_archived():
    global api_overall_progress
    global archived_progress
    api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("Getting archived...\n{task.description}"),
        console=console_.get_temp_console(),
    )
    archived_progress = Progress("{task.description}")
    progress_group = Group(api_overall_progress, Panel(Group(archived_progress)))
    return Live(
        progress_group,
        refresh_per_second=5,
        console=console_.get_shared_console(),
        transient=True,
    )


def set_up_api_stories():
    global api_overall_progress
    global stories_progress
    api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("Getting stories...\n{task.description}"),
        console=console_.get_temp_console(),
    )
    stories_progress = Progress("{task.description}")
    progress_group = Group(api_overall_progress, Panel(Group(stories_progress)))
    return Live(
        progress_group,
        refresh_per_second=5,
        console=console_.get_shared_console(),
        transient=True,
    )


def set_up_api_highlights_lists():
    global api_overall_progress
    global highlights_progress
    api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("Getting highlights lists...\n{task.description}"),
    )
    highlights_progress = Progress("{task.description}")
    progress_group = Group(api_overall_progress, Panel(Group(highlights_progress)))
    return Live(
        progress_group,
        refresh_per_second=5,
        console=console_.get_shared_console(),
        transient=True,
    )


def set_up_api_highlights():
    global api_overall_progress
    global highlights_progress
    api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("Getting highlights via list..\n{task.description}"),
    )
    highlights_progress = Progress("{task.description}")
    progress_group = Group(api_overall_progress, Panel(Group(highlights_progress)))
    return Live(
        progress_group,
        refresh_per_second=5,
        console=console_.get_shared_console(),
        transient=True,
    )


def set_up_api_labels():
    global api_overall_progress
    global labelled_progress
    api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("Getting Labels\n{task.description}"),
        console=console_.get_temp_console(),
    )
    labelled_progress = Progress("{task.description}")
    progress_group = Group(api_overall_progress, Panel(Group(labelled_progress)))
    return Live(
        progress_group,
        refresh_per_second=5,
        console=console_.get_shared_console(),
        transient=True,
    )


def set_up_api_posts_labels():
    global api_overall_progress
    global labelled_progress
    api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("Getting Posts via labels\n{task.description}"),
        console=console_.get_temp_console(),
    )
    labelled_progress = Progress("{task.description}")
    progress_group = Group(api_overall_progress, Panel(Group(labelled_progress)))
    return Live(
        progress_group,
        refresh_per_second=5,
        console=console_.get_shared_console(),
        transient=True,
    )


def update_activity_task(**kwargs):
    global activity_task
    activity_progress.update(
           activity_task, **kwargs
    )

def increment_activity_count():
    global activity_counter_task
    activity_counter.update(
           activity_counter_task,advance=1
    )


def update_activity_count(**kwargs):
    global activity_counter_task
    activity_counter.update(
           activity_counter_task,**kwargs
    )
#switchers
def switch_api_progress():
    global api_progress_group
    global live
    if not api_progress_group:
        return
    live.update(api_progress_group,refresh=True)

def add_user_first_activity(**kwargs):
    global user_first_task
    global activity_counter
    user_first_task=activity_counter.add_task(
            **kwargs
    )

def increment_user_first_activity():
    global user_first_task
    global activity_progress
    activity_counter.update(
           user_first_task,advance=1
    )

def update_first_activity(**kwargs):
    global user_first_task
    global activity_counter_task
    activity_counter.update(
          user_first_task,  **kwargs
    )