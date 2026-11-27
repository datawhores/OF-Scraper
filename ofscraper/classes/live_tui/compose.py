import contextlib
import threading

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, RichLog, Static

from ofscraper.classes.table.sections.table import DataTableExtended


class LiveConsole(RichLog):
    """Thread-safe RichLog sink for OF-Scraper's shared TextHandler."""

    def on_unmount(self) -> None:
        import ofscraper.utils.logs.logger as logger

        logger.remove_widget(self)

    def write(self, *args, **kwargs):
        if not self.is_mounted:
            return self
        app_thread = getattr(self.app, "_thread_id", None)
        if app_thread is not None and app_thread != threading.get_ident():
            with contextlib.suppress(RuntimeError):
                self.app.call_from_thread(super().write, *args, **kwargs)
            return self
        return super().write(*args, **kwargs)


class LiveStreamTable(DataTableExtended):
    COPY_COLUMNS = {"username", "detail"}


def compose_live_tui():
    with Horizontal(id="telemetry_bar"):
        yield Static("", id="telemetry_left", classes="telemetry_col", markup=True)
        yield Static("", id="telemetry_mid", classes="telemetry_col", markup=True)
        yield Static("", id="telemetry_right", classes="telemetry_col", markup=True)

    with Vertical(id="action_bar"):
        with Horizontal(id="action_row_1", classes="action_row"):
            yield Button("Poll Now (p)", id="btn_poll", compact=True, variant="primary")
            yield Button("Start All (a)", id="btn_start_all", compact=True, variant="success")
            yield Button("Stop All (S)", id="btn_stop_all", compact=True, variant="warning")
            yield Button("Pause Polls (Space)", id="btn_pause", compact=True)
            yield Button("Slots -", id="btn_slots_down", compact=True)
            yield Button("Slots +", id="btn_slots_up", compact=True)
        with Horizontal(id="action_row_2", classes="action_row"):
            yield Button("Following: ON (w)", id="btn_toggle_following", compact=True, variant="success")
            yield Button("+ Add User (u)", id="btn_show_add_user", compact=True, variant="primary")
            yield Button("Chat: OFF (c)", id="btn_toggle_chat", compact=True)
            yield Button("Filter: Online (f)", id="btn_filter_active", compact=True, variant="success")
            yield Button("Clear Ended (x)", id="btn_clear_ended", compact=True)
            yield Button("Stop & Quit (q)", id="btn_quit", compact=True, variant="error")
        with Horizontal(id="add_user_bar", classes="-hidden"):
            yield Input(
                placeholder="Enter username(s) separated by comma or space, then press Enter...",
                id="add_user_input",
            )
            yield Button("Track", id="btn_submit_add_user", compact=True, variant="success")
            yield Button("Cancel", id="btn_cancel_add_user", compact=True)

    with Vertical(id="streams_container"):
        yield LiveStreamTable(id="streams_table")

    with Horizontal(id="bottom_split"):
        with Vertical(id="log_pane", classes="pane_box"):
            yield Static("Activity & Scraper Logs", classes="pane_title")
            yield LiveConsole(id="live_console", wrap=True, highlight=True, markup=True)
        with Vertical(id="chat_pane", classes="pane_box"):
            yield Static("Fansly Live Chat (--live-chat)", id="chat_pane_title", classes="pane_title")
            yield RichLog(id="live_chat_log", wrap=True, highlight=False, markup=False)

    yield Static(
        "[bold cyan]Click Cell[/bold cyan] [Stop/Resume] / [Remove] / [Folder]  "
        "[bold cyan]p[/bold cyan] Poll  "
        "[bold cyan]w[/bold cyan] Following  "
        "[bold cyan]u[/bold cyan] Add User  "
        "[bold cyan]a / S[/bold cyan] Start/Stop All  "
        "[bold cyan]s / r / d / o[/bold cyan] Row Actions  "
        "[bold cyan]c[/bold cyan] Chat  "
        "[bold cyan]f[/bold cyan] Filter  "
        "[bold cyan]q[/bold cyan] Quit",
        id="keybind_footer",
        markup=True,
    )
