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


def get_api_progress_Group():
    global timeline_layout
    global pinned_layout
    global archived_layout
    global labelled_layout
    global messages_layout
    global paid_layout
    global stories_layout
    global highlights_layout
    set_up_progress()
    setup_layout()

    layout = Layout(name="parent")
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

    progress_group = Group(overall_progress, layout)
    return progress_group


def setup_layout(visible=None):
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


def set_up_progress():
    global timeline_progress
    global pinned_progress
    global overall_progress
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
