import aioprocessing
from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.style import Style

timeline_progress = None
pinned_progress = None
overall_progress = None
archived_progress = None
paid_progress = None
labelled_progress = None
stories_progress = None
highlights_progress = None
messages = None
shared_data = None
shared_queue = None
# layout=None


def set_up_manager():
    global shared_data
    shared_data = {
        "timeline_progress": timeline_progress,
        "pinned_progress": pinned_progress,
        "overall_progress": overall_progress,
        "archived_progress": archived_progress,
        "messages_progress": messages_progress,
        "paid_progress": paid_progress,
        "labelled_progress": labelled_progress,
        "highlights_progress": highlights_progress,
        "stories_progress": stories_progress,
        "timeline_layout": timeline_layout,
        "pinned_layout": pinned_layout,
        "archived_layout": archived_layout,
        "labelled_layout": labelled_layout,
        "messages_layout": messages_layout,
        "paid_layout": paid_layout,
        "stories_layout": stories_layout,
        "highlights_layout": highlights_layout,
    }


def get_api_progress_Group():
    global timeline_layout
    global pinned_layout
    global archived_layout
    global labelled_layout
    global messages_layout
    global paid_layout
    global stories_layout
    global highlights_layout
    global shared_queue
    shared_queue = aioprocessing.AioQueue()
    set_up_progress()
    setup_layout()
    set_up_manager()

    layout = Layout(name="parent")
    layout.split_column(Layout(name="upper"), Layout(name="lower"))
    layout["upper"].split_row(
        timeline_layout, pinned_layout, archived_layout, labelled_layout
    ),
    layout["lower"].split_row(
        messages_layout, paid_layout, stories_layout, highlights_layout
    )

    progress_group = Group(overall_progress, layout)
    return progress_group


def setup_layout():
    global timeline_progress
    global pinned_progress
    global overall_progress
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

    timeline_layout = Layout(Panel(timeline_progress), name="timeline")
    pinned_layout = Layout(Panel(pinned_progress), name="pinned")
    archived_layout = Layout(Panel(archived_progress), name="archived")
    labelled_layout = Layout(Panel(labelled_progress), name="labelled")
    messages_layout = Layout(Panel(messages_progress), name="messages")
    paid_layout = Layout(Panel(paid_progress), name="paid")
    stories_layout = Layout(Panel(stories_progress), name="stories")
    highlights_layout = Layout(Panel(highlights_progress), name="highlights")


def set_up_progress():
    global timeline_progress
    global pinned_progress
    global overall_progress
    global layout
    global archived_progress
    global messages_progress
    global paid_progress
    global labelled_progress
    global highlights_progress
    global stories_progress
    timeline_progress = Progress("{task.description}")
    pinned_progress = Progress("{task.description}")
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("{task.description}"),
    )
    archived_progress = Progress("{task.description}")
    messages_progress = Progress("{task.description}")
    paid_progress = Progress("{task.description}")
    labelled_progress = Progress("{task.description}")
    highlights_progress = Progress("{task.description}")
    stories_progress = Progress("{task.description}")
