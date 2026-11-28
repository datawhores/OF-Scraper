import contextlib
import datetime
import logging
import os
import pathlib
import re
import shutil
import subprocess
import threading
import time
from collections import deque

from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.css.query import NoMatches
from textual.widgets import Button, Input, RichLog, Static
from textual.widgets.data_table import CellDoesNotExist

import ofscraper.utils.events as of_events
from ofscraper.classes.live_tui.compose import compose_live_tui
from ofscraper.classes.live_tui.css import LIVE_CSS
from ofscraper.classes.live_tui.formatters import (
    COLUMNS,
    _epoch_seconds,
    format_cells,
    format_telemetry,
    sort_key_for_entry,
)
from ofscraper.classes.live_tui.state import (
    ONLINE_STATUSES,
    RECORDING_STATUSES,
    RESUMABLE_STATUSES,
    STOPPABLE_STATUSES,
    TICK_STATUSES,
    LiveStore,
    StreamRowState,
)
from ofscraper.classes.table.sections.table import DataTableExtended

log = logging.getLogger("shared")

__all__ = [
    "LiveStreamApp",
    "ONLINE_STATUSES",
    "RECORDING_STATUSES",
    "StreamRowState",
    "run_live_tui",
]


def _resolve_entry_target(entry: StreamRowState | None):
    import ofscraper.classes.placeholder as placeholder
    import ofscraper.classes.table.utils.open_folder as open_folder
    import ofscraper.sites as sites
    import ofscraper.utils.paths.common as common_paths
    from ofscraper.sites.fansly.live import folder_name

    save_root = pathlib.Path(common_paths.get_save_location()).expanduser()
    live_root = pathlib.Path(placeholder.live_save_location(save_root)).expanduser()

    if entry is not None:
        existing = entry.latest_existing_file()
        if existing is not None:
            return open_folder.Target(open_folder.absolute(existing), select=True)
        site_dir = "Fansly" if entry.site == "Fansly" else "OnlyFans"
        ext = "mp4" if entry.site == "Fansly" else "webm"
        when = (
            datetime.datetime.fromtimestamp(entry.started_epoch, tz=datetime.timezone.utc)
            if entry.started_epoch
            else datetime.datetime.now(datetime.timezone.utc)
        )
        live_dir = placeholder.live_recording_path(
            save_root,
            folder_name(entry.username),
            when,
            site_name=site_dir,
            ext=ext,
            model_id=entry.account_id,
        ).parent
        creator_dir = live_dir.parent
        site_root = live_root / site_dir
        for candidate in (live_dir, creator_dir, site_root, live_root, save_root):
            if candidate.is_dir():
                return open_folder.Target(open_folder.absolute(candidate))
        return open_folder.Target(open_folder.absolute(live_dir))

    site_root = live_root / ("Fansly" if sites.is_fansly() else "OnlyFans")
    chosen = site_root if site_root.is_dir() else (live_root if live_root.is_dir() else save_root)
    return open_folder.Target(open_folder.absolute(chosen))


def _open_in_vscode(folder: pathlib.Path) -> bool:
    if not folder.is_dir() or not shutil.which("code"):
        return False
    # Build a local env for the VS Code fallback without mutating os.environ
    sub_env = os.environ.copy()
    uid = os.getuid() if hasattr(os, "getuid") else None
    if uid is not None:
        runtime_dir = pathlib.Path(f"/run/user/{uid}")
        if not sub_env.get("WAYLAND_DISPLAY") and runtime_dir.is_dir():
            wl = [
                w
                for w in sorted(runtime_dir.glob("wayland-[0-9]*"))
                if not w.name.endswith(".lock")
            ]
            if wl:
                sub_env["WAYLAND_DISPLAY"] = wl[0].name
        dbus_key = "DBUS_SESSION_BUS_ADDRESS"
        if not sub_env.get(dbus_key) and (runtime_dir / "bus").exists():
            sub_env[dbus_key] = f"unix:path=/run/user/{uid}/bus"
    if not sub_env.get("DISPLAY"):
        x_socks = sorted(pathlib.Path("/tmp/.X11-unix").glob("X[0-9]*"))
        if x_socks:
            sub_env["DISPLAY"] = f":{x_socks[0].name[1:]}"
    try:
        proc = subprocess.Popen(
            ["code", "--new-window", str(folder)],
            env=sub_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        return False
    threading.Thread(target=proc.wait, daemon=True).start()
    return True


class LiveStreamApp(App):
    CSS = LIVE_CSS
    BINDINGS = [
        Binding("p", "poll_now", "Poll Now"),
        Binding("w", "toggle_following", "Toggle Following"),
        Binding("u", "show_add_user", "Add User"),
        Binding("d", "remove_creator", "Remove User"),
        Binding("a", "start_all", "Start All"),
        Binding("S", "stop_all", "Stop All"),
        Binding("s", "stop_creator", "Stop Creator"),
        Binding("r", "resume_creator", "Resume Creator"),
        Binding("space", "toggle_pause", "Pause Polls"),
        Binding("minus", "slots_down", "Slots -"),
        Binding("plus", "slots_up", "Slots +"),
        Binding("equals_sign", "slots_up", "Slots +", show=False),
        Binding("c", "toggle_chat", "Toggle Chat"),
        Binding("o", "open_folder", "Open Folder"),
        Binding("f", "toggle_active_only", "Filter"),
        Binding("slash", "show_search", "Search"),
        Binding("escape", "dismiss_bars", "Clear Search", show=False),
        Binding("x", "clear_ended", "Clear Ended"),
        Binding("q", "quit_tui", "Quit"),
        Binding("ctrl+x", "abort_tui", "Stop & Quit", priority=True),
    ]

    def __init__(self, watch: bool, runner=None) -> None:
        super().__init__()
        import ofscraper.sites as sites

        self.watch = watch
        self.runner = runner
        self._live_thread = None
        self._watcher = None
        self._watcher_loop = None

        self._site_label = "Fansly" if sites.is_fansly() else "OnlyFans"
        self._include_following = True
        self._chat_enabled = False
        self._max_concurrent = 2
        self._interval = 60
        self._jitter = 10
        self._paused = False
        self._poll_state = "starting"
        self._poll_count = 0
        self._next_poll_deadline: float | None = None
        self._last_error: str | None = None

        self._store = LiveStore()
        self._active_chat_user: str | None = None
        self._shown_keys: set[str] = set()
        self._filter_mode = "online"
        self._search_query: str = ""
        self._sort_key = "status"
        self._sort_reverse = False

        self._stopping = False
        self._user_aborted = False

    @property
    def _streams(self) -> dict[str, StreamRowState]:
        return self._store.streams

    @_streams.setter
    def _streams(self, value: dict[str, StreamRowState]) -> None:
        self._store.streams = value

    @property
    def _username_index(self) -> dict[tuple[str, str], str]:
        return self._store.username_index

    @_username_index.setter
    def _username_index(self, value: dict[tuple[str, str], str]) -> None:
        self._store.username_index = value

    @property
    def _removed_keys(self) -> set[str]:
        return self._store.removed_keys

    @property
    def _removed_user_ids(self) -> dict[tuple[str, str], str]:
        return self._store.removed_user_ids

    @property
    def _chat_buffers(self) -> dict[str, deque[Text]]:
        return self._store.chat_buffers

    def compose(self):
        yield from compose_live_tui()

    def on_ready(self) -> None:
        import ofscraper.sites as sites
        import ofscraper.utils.console as console_
        import ofscraper.utils.logs.logger as logger
        from ofscraper.sites.fansly import live as shared_live

        opts = shared_live.options()
        self._include_following = shared_live.wants_all_usernames(opts.get("usernames"))
        self._chat_enabled = bool(opts.get("chat")) and sites.is_fansly()
        self._max_concurrent = int(opts.get("max_concurrent") or 2)
        self._interval = int(opts.get("interval") or 60)
        self._jitter = int(opts.get("jitter") or 0)

        self._init_table()
        self._sync_following_button()
        self._sync_chat_button()
        self._sync_filter_button()

        logger.add_widget(self.query_one("#live_console"))
        console_.get_shared_console().quiet = True

        of_events.subscribe("live_watcher", self._ev_watcher)
        of_events.subscribe("live_poll", self._ev_poll)
        of_events.subscribe("live_stream", self._ev_stream)
        of_events.subscribe("live_chat", self._ev_chat)

        self._live_thread = shared_live.LiveThread(self.watch, self.runner)
        self._live_thread.start()
        self.set_interval(1.0, self._on_tick)
        self._refresh_telemetry()
        self.set_focus(self.query_one("#streams_table"))

    def on_unmount(self) -> None:
        of_events.unsubscribe("live_watcher", self._ev_watcher)
        of_events.unsubscribe("live_poll", self._ev_poll)
        of_events.unsubscribe("live_stream", self._ev_stream)
        of_events.unsubscribe("live_chat", self._ev_chat)

    @property
    def _is_input_open(self) -> bool:
        try:
            return (
                not self.query_one("#add_user_bar").has_class("-hidden")
                or not self.query_one("#search_bar").has_class("-hidden")
            )
        except NoMatches:
            return False

    # ------------------------------------------------------------------ thread bridge

    def _ui_dispatch(self, fn, *args, **kwargs):
        if getattr(self, "_thread_id", None) == threading.get_ident():
            fn(*args, **kwargs)
        else:
            with contextlib.suppress(RuntimeError):
                self.call_from_thread(fn, *args, **kwargs)

    def _call_watcher(self, fn, *args) -> bool:
        loop = self._watcher_loop
        if self._watcher is None or loop is None:
            return False
        try:
            loop.call_soon_threadsafe(fn, *args)
            return True
        except RuntimeError:
            return False

    # ------------------------------------------------------------------ event handlers

    def _ev_watcher(self, **kw):
        self._ui_dispatch(self._handle_watcher, kw)

    def _ev_poll(self, **kw):
        self._ui_dispatch(self._handle_poll, kw)

    def _ev_stream(self, **kw):
        self._ui_dispatch(self._handle_stream, kw)

    def _ev_chat(self, **kw):
        self._ui_dispatch(self._handle_chat, kw)

    def _handle_watcher(self, kw: dict):
        state = kw.get("state")
        if state == "started":
            self._watcher = kw.get("watcher")
            self._watcher_loop = kw.get("loop")
            if kw.get("site"):
                self._site_label = (
                    "Fansly" if str(kw["site"]).lower() == "fansly" else "OnlyFans"
                )
            self._max_concurrent = int(kw.get("max_concurrent") or self._max_concurrent)
            self._interval = int(kw.get("interval") or self._interval)
            if self._watcher is not None:
                self._include_following = bool(
                    getattr(self._watcher, "include_following", self._include_following)
                )
            self._sync_following_button()
            self._sync_chat_button()
        elif state == "stopped":
            self._watcher = None
            self._watcher_loop = None
            self._poll_state = "finished"
            self._next_poll_deadline = None
        self._refresh_telemetry()

    def _handle_poll(self, kw: dict):
        state = kw.get("state")
        if state == "polling":
            self._poll_state = "polling"
            self._next_poll_deadline = None
        elif state == "targets":
            site = str(kw.get("site") or self._site_label).lower()
            self._store.apply_targets(site, kw.get("targets"))
            self._rebuild_table()
        elif state == "ok":
            self._poll_count += 1
            self._poll_state = "idle"
            self._last_error = None
            site = str(kw.get("site") or self._site_label).lower()
            self._store.apply_poll_ok(site, kw.get("online"), parse_epoch=_epoch_seconds)
            self._rebuild_table()
        elif state == "error":
            self._poll_count += 1
            self._poll_state = "error"
            self._last_error = str(kw.get("error") or "poll failed")
        elif state == "waiting":
            self._paused = bool(kw.get("paused", self._paused))
            self._max_concurrent = int(kw.get("max_concurrent") or self._max_concurrent)
            timeout = float(kw.get("timeout") or 0.0)
            self._poll_state = "paused" if self._paused else "waiting"
            self._next_poll_deadline = (
                None if self._paused else (time.monotonic() + timeout)
            )
        self._refresh_telemetry()

    def _handle_stream(self, kw: dict):
        site = str(kw.get("site") or self._site_label).lower()
        entry, was_status, new_status = self._store.apply_stream_event(
            site, kw, parse_epoch=_epoch_seconds
        )
        if entry is None:
            return
        now_matches = self._store.should_show(
            entry, self._filter_mode, self._search_query
        )
        was_shown = entry.key in self._shown_keys
        if now_matches != was_shown or (
            now_matches and was_status != new_status and self._sort_key == "status"
        ):
            self._rebuild_table()
        elif now_matches:
            self._upsert_row(entry)
        self._refresh_telemetry()

    def _handle_chat(self, kw: dict):
        username = str(kw.get("username") or "").strip()
        sender = str(kw.get("sender") or "user")
        content = str(kw.get("content") or "").strip()
        total = kw.get("total_received")
        ukey = username.lower()

        line = None
        stamp = ""
        if content:
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            line = Text()
            line.append(f"[{stamp}] ", style="dim")
            line.append(
                f"{sender}: ",
                style="bold bright_green" if sender != "system" else "bold cyan",
            )
            line.append(content)

        updated_entry = self._store.record_chat(username, total, line)
        if updated_entry is not None:
            self._upsert_row(updated_entry)

        if line is not None:
            selected = self._selected_entry()
            target_user = selected.username.lower() if selected else None
            if self._active_chat_user != target_user:
                self._sync_chat_pane(force=True)
            elif target_user == ukey or target_user is None:
                try:
                    chat_widget = self.query_one("#live_chat_log", RichLog)
                except NoMatches:
                    return
                if target_user is None and username:
                    line_all = Text()
                    line_all.append(f"[{stamp}] ", style="dim")
                    line_all.append(f"@{username} ", style="bold cyan")
                    line_all.append(f"{sender}: ", style="bold bright_green")
                    line_all.append(content)
                    chat_widget.write(line_all, scroll_end=True)
                else:
                    chat_widget.write(line, scroll_end=True)
                    self._update_chat_title(selected)

    def _update_chat_title(self, entry: StreamRowState | None) -> None:
        try:
            title_widget = self.query_one("#chat_pane_title", Static)
        except NoMatches:
            return
        if entry is None:
            title_widget.update("Fansly Live Chat (--live-chat)")
        elif entry.site != "Fansly":
            title_widget.update(f"Live Chat — @{entry.username} (Fansly only)")
        else:
            title_widget.update(
                f"Fansly Live Chat — @{entry.username} ({entry.chat_count} msg)"
            )

    def _sync_chat_pane(self, force: bool = False) -> None:
        entry = self._selected_entry()
        target_user = entry.username.lower() if entry else None
        if not force and target_user == self._active_chat_user:
            self._update_chat_title(entry)
            return
        self._active_chat_user = target_user
        self._update_chat_title(entry)
        try:
            chat_widget = self.query_one("#live_chat_log", RichLog)
        except NoMatches:
            return
        chat_widget.clear()
        if target_user and target_user in self._chat_buffers:
            for line in self._chat_buffers[target_user]:
                chat_widget.write(line, scroll_end=True)

    # ------------------------------------------------------------------ table & periodic tick

    def _init_table(self):
        table = self.query_one("#streams_table", DataTableExtended)
        table.clear(True)
        table.fixed_rows = 0
        table.zebra_stripes = True
        table.cursor_type = "cell"
        for col_key, title, width in COLUMNS:
            arrow = ""
            if col_key == self._sort_key:
                arrow = " ▼" if self._sort_reverse else " ▲"
            table.add_column(f"{title}{arrow}", key=col_key, width=width)
        self._shown_keys.clear()

    def _visible_entries(self, now_wall: float | None = None) -> list[StreamRowState]:
        wall = time.time() if now_wall is None else now_wall
        rows = [
            r
            for r in self._streams.values()
            if self._store.should_show(r, self._filter_mode, self._search_query)
        ]
        rows.sort(
            key=lambda r: sort_key_for_entry(r, self._sort_key, wall),
            reverse=self._sort_reverse,
        )
        return rows

    def _format_cells(self, entry: StreamRowState, now_wall: float) -> dict[str, Text]:
        return format_cells(entry, now_wall, chat_enabled=self._chat_enabled)

    def _upsert_row(self, entry: StreamRowState):
        table = self.query_one("#streams_table", DataTableExtended)
        if not self._store.should_show(entry, self._filter_mode, self._search_query):
            if entry.key in self._shown_keys:
                self._rebuild_table()
            return
        cells = self._format_cells(entry, time.time())
        if entry.key not in self._shown_keys:
            table.add_row(*(cells[col] for col, _, _ in COLUMNS), key=entry.key)
            self._shown_keys.add(entry.key)
        else:
            for col, _, _ in COLUMNS:
                table.update_cell_at_key(entry.key, col, cells[col])

    def _rebuild_table(self):
        selected_key = self._selected_row_key()
        table = self.query_one("#streams_table", DataTableExtended)
        prev_col = table.cursor_column
        self._init_table()
        now_wall = time.time()
        restore_idx = None
        for idx, entry in enumerate(self._visible_entries(now_wall)):
            cells = self._format_cells(entry, now_wall)
            table.add_row(*(cells[col] for col, _, _ in COLUMNS), key=entry.key)
            self._shown_keys.add(entry.key)
            if entry.key == selected_key:
                restore_idx = idx
        if restore_idx is not None:
            with contextlib.suppress(IndexError, CellDoesNotExist):
                table.move_cursor(row=restore_idx, column=prev_col)
        self._sync_chat_pane()

    def _on_tick(self):
        now_mono = time.monotonic()
        now_wall = time.time()
        table = self.query_one("#streams_table", DataTableExtended)

        for entry in self._streams.values():
            if entry.status in TICK_STATUSES:
                entry.refresh_disk_metrics(now_mono)
                if entry.key in self._shown_keys:
                    cells = self._format_cells(entry, now_wall)
                    for col in ("uptime", "saved", "speed", "parts", "chat"):
                        table.update_cell_at_key(entry.key, col, cells[col])

        if (
            self._live_thread
            and self._live_thread.finished.is_set()
            and self._poll_state != "finished"
        ):
            self._poll_state = "finished"

        self._refresh_telemetry()

    def _refresh_telemetry(self):
        recording, online_cnt, queued, total_bytes, total_speed = (
            self._store.telemetry_counts()
        )
        left, mid, right = format_telemetry(
            site_label=self._site_label,
            watch=self.watch,
            interval=self._interval,
            chat_enabled=self._chat_enabled,
            poll_count=self._poll_count,
            recording=recording,
            max_concurrent=self._max_concurrent,
            online_cnt=online_cnt,
            queued=queued,
            stopping=self._stopping,
            poll_state=self._poll_state,
            paused=self._paused,
            next_poll_deadline=self._next_poll_deadline,
            last_error=self._last_error,
            total_bytes=total_bytes,
            total_speed=total_speed,
            now_mono=time.monotonic(),
        )
        self.query_one("#telemetry_left", Static).update(left)
        self.query_one("#telemetry_mid", Static).update(mid)
        self.query_one("#telemetry_right", Static).update(right)

    # ------------------------------------------------------------------ user actions

    def _selected_row_key(self) -> str | None:
        try:
            table = self.query_one("#streams_table", DataTableExtended)
        except NoMatches:
            return None
        if table.row_count == 0:
            return None
        try:
            return table.coordinate_to_cell_key(
                Coordinate(table.cursor_row, 0)
            ).row_key.value
        except (CellDoesNotExist, IndexError):
            return None

    def _selected_entry(self) -> StreamRowState | None:
        return self._store.get(self._selected_row_key())

    def on_data_table_header_selected(self, event) -> None:
        col_key = getattr(getattr(event, "column_key", None), "value", None)
        if not col_key or col_key.startswith("act_"):
            return
        if self._sort_key == col_key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_key = col_key
            self._sort_reverse = col_key in {
                "saved",
                "speed",
                "uptime",
                "parts",
                "chat",
            }
        self._rebuild_table()

    def on_data_table_cell_highlighted(self, event) -> None:
        self._sync_chat_pane()

    def on_data_table_row_highlighted(self, event) -> None:
        self._sync_chat_pane()

    def on_data_table_cell_selected(self, event) -> None:
        table = event.control
        col_key = table.ordered_columns_keys[event.coordinate.column]
        row_key = event.cell_key.row_key.value
        entry = self._store.get(row_key)
        if entry is None:
            return
        if col_key == "act_toggle":
            if entry.status in STOPPABLE_STATUSES:
                self._stop_entry(entry)
            elif entry.status in RESUMABLE_STATUSES:
                self._resume_entry(entry)
        elif col_key == "act_remove":
            self._remove_entry(entry)
        elif col_key == "act_folder":
            self._open_entry_folder(entry)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "add_user_input":
            self._submit_add_user()
        elif event.input.id == "search_input":
            self._hide_search_bar()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "search_input":
            return
        q = event.value.strip().lstrip("@").lower()
        if q == self._search_query:
            return
        self._search_query = q
        self._sync_search_button()
        self._rebuild_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        dispatch = {
            "btn_poll": self.action_poll_now,
            "btn_toggle_following": self.action_toggle_following,
            "btn_show_add_user": self.action_show_add_user,
            "btn_submit_add_user": self._submit_add_user,
            "btn_cancel_add_user": self._hide_add_user,
            "btn_search": self.action_show_search,
            "btn_done_search": self._hide_search_bar,
            "btn_clear_search": self._clear_search,
            "btn_start_all": self.action_start_all,
            "btn_stop_all": self.action_stop_all,
            "btn_pause": self.action_toggle_pause,
            "btn_slots_down": self.action_slots_down,
            "btn_slots_up": self.action_slots_up,
            "btn_toggle_chat": self.action_toggle_chat,
            "btn_filter_active": self.action_toggle_active_only,
            "btn_clear_ended": self.action_clear_ended,
            "btn_quit": self.action_quit_tui,
        }
        fn = dispatch.get(event.button.id)
        if fn:
            fn()

    def _sync_following_button(self) -> None:
        btn = self.query_one("#btn_toggle_following", Button)
        scope = "Following" if self._site_label == "Fansly" else "Subscribed"
        if self._include_following:
            btn.label = f"{scope}: ON (w)"
            btn.variant = "success"
        else:
            btn.label = f"{scope}: OFF (w)"
            btn.variant = "default"

    def action_toggle_following(self) -> None:
        if self._is_input_open:
            return
        if not self._watcher:
            self.notify("Watcher is not active right now.", severity="warning")
            return
        self._include_following = not self._include_following
        self._call_watcher(self._watcher.set_include_following, self._include_following)
        self._sync_following_button()
        scope = (
            "followed creators"
            if self._site_label == "Fansly"
            else "active subscriptions"
        )
        if not self._include_following:
            extra = set(getattr(self._watcher, "extra_usernames", None) or ())
            self._store.drop_offline_except(extra)
            self._rebuild_table()
            self.notify(f"Excluded {scope}; tracking explicit usernames only.")
        else:
            self.notify(f"Included all {scope}; polling now...")

    def action_show_add_user(self) -> None:
        self.query_one("#search_bar").add_class("-hidden")
        bar = self.query_one("#add_user_bar")
        bar.remove_class("-hidden")
        inp = self.query_one("#add_user_input", Input)
        inp.value = ""
        self.set_focus(inp)

    def _hide_add_user(self) -> None:
        self.query_one("#add_user_bar").add_class("-hidden")
        self.set_focus(self.query_one("#streams_table"))

    def _sync_search_button(self) -> None:
        btn = self.query_one("#btn_search", Button)
        if self._search_query:
            q = self._search_query
            short = f"{q[:12]}…" if len(q) > 12 else q
            btn.label = Text(f"Search: {short} (/)")
            btn.variant = "warning"
        else:
            btn.label = "Search (/)"
            btn.variant = "default"

    def action_show_search(self) -> None:
        if not self.query_one("#add_user_bar").has_class("-hidden"):
            self.query_one("#add_user_bar").add_class("-hidden")
        bar = self.query_one("#search_bar")
        bar.remove_class("-hidden")
        inp = self.query_one("#search_input", Input)
        if inp.value.strip().lstrip("@").lower() != self._search_query:
            inp.value = self._search_query
        with contextlib.suppress(Exception):
            inp.cursor_position = len(inp.value)
        self.set_focus(inp)

    def _hide_search_bar(self) -> None:
        self.query_one("#search_bar").add_class("-hidden")
        self.set_focus(self.query_one("#streams_table"))

    def _clear_search(self) -> None:
        had_query = bool(self._search_query)
        self._search_query = ""
        inp = self.query_one("#search_input", Input)
        if inp.value:
            inp.value = ""
        self.query_one("#search_bar").add_class("-hidden")
        self._sync_search_button()
        if had_query:
            self._rebuild_table()
        self.set_focus(self.query_one("#streams_table"))

    def action_dismiss_bars(self) -> None:
        if not self.query_one("#add_user_bar").has_class("-hidden"):
            self._hide_add_user()
        elif not self.query_one("#search_bar").has_class("-hidden") or self._search_query:
            self._clear_search()

    def _submit_add_user(self) -> None:
        inp = self.query_one("#add_user_input", Input)
        raw = inp.value.strip()
        self._hide_add_user()
        if not raw:
            return
        names = [
            part.lstrip("@").strip()
            for part in re.split(r"[,\s]+", raw)
            if part.lstrip("@").strip()
        ]
        if not names:
            return
        if not self._watcher:
            self.notify("Watcher is not active right now.", severity="warning")
            return
        self._store.restore_usernames(self._site_label.lower(), names)
        self._call_watcher(self._watcher.add_usernames, names)
        self.notify(
            f"Added {', '.join(names)} to live watchlist; checking now...", markup=False
        )

    def _remove_entry(self, entry: StreamRowState) -> None:
        if not self._watcher:
            self.notify("Watcher has already finished.", severity="warning")
            return
        self._store.remove_entry(entry)
        self._call_watcher(
            self._watcher.remove_username, entry.username, entry.account_id
        )
        self._rebuild_table()
        self._refresh_telemetry()
        self.notify(f"Removed @{entry.username} from tracking.", markup=False)

    def action_remove_creator(self) -> None:
        if self._is_input_open:
            return
        entry = self._selected_entry()
        if entry is None:
            self.notify("Highlight a creator row first.", severity="warning")
            return
        self._remove_entry(entry)

    def action_poll_now(self) -> None:
        if self._is_input_open:
            return
        if self._watcher and self._call_watcher(self._watcher.request_poll):
            self.notify("Checking for live streams now...")
        else:
            self.notify("Watcher is not active right now.", severity="warning")

    def _stop_entry(self, entry: StreamRowState) -> None:
        if not self._watcher:
            self.notify("Watcher has already finished.", severity="warning")
            return
        if self._store.mark_stopped(entry):
            self._upsert_row(entry)
            self._call_watcher(self._watcher.stop_creator, entry.account_id)
            self.notify(f"Stopping {entry.username}...", markup=False)
        else:
            self.notify(f"{entry.username} is not currently active.", markup=False)

    def _resume_entry(self, entry: StreamRowState) -> None:
        if not self._watcher:
            self.notify("Watcher has already finished.", severity="warning")
            return
        if self._store.mark_resumed(entry):
            self._upsert_row(entry)
            self._call_watcher(self._watcher.resume_creator, entry.account_id)
            self.notify(f"Resuming {entry.username}...", markup=False)
        else:
            self.notify(f"{entry.username} is not stopped.", markup=False)

    def action_stop_creator(self) -> None:
        if self._is_input_open:
            return
        entry = self._selected_entry()
        if entry is None:
            self.notify("Highlight a creator row first.", severity="warning")
            return
        self._stop_entry(entry)

    def action_resume_creator(self) -> None:
        if self._is_input_open:
            return
        entry = self._selected_entry()
        if entry is None:
            self.notify("Highlight a creator row first.", severity="warning")
            return
        self._resume_entry(entry)

    def action_stop_all(self) -> None:
        if self._is_input_open:
            return
        if not self._watcher:
            self.notify("Watcher has already finished.", severity="warning")
            return
        active_entries = self._store.stop_all()
        ids = [e.account_id for e in active_entries]
        self._call_watcher(self._watcher.stop_all, ids)
        self._rebuild_table()
        self._refresh_telemetry()
        self.notify(f"Stopping {len(active_entries)} active/online stream(s)...")

    def action_start_all(self) -> None:
        if self._is_input_open:
            return
        if not self._watcher:
            self.notify("Watcher has already finished.", severity="warning")
            return
        self._store.resume_all()
        self._call_watcher(self._watcher.resume_all)
        self._rebuild_table()
        self._refresh_telemetry()
        self.notify("Resumed all creators and polling now...")

    def action_toggle_pause(self) -> None:
        if self._is_input_open:
            return
        if not self.watch:
            self.notify("One-shot (--live) mode does not repeat polls.")
            return
        if not self._watcher:
            return
        self._paused = not self._paused
        self._call_watcher(self._watcher.set_paused, self._paused)
        btn = self.query_one("#btn_pause", Button)
        btn.label = "Resume Polls (Space)" if self._paused else "Pause Polls (Space)"
        btn.variant = "warning" if self._paused else "default"
        self._refresh_telemetry()

    def action_slots_down(self) -> None:
        if self._is_input_open:
            return
        active_count = self._store.recording_count()
        floor = max(1, active_count)
        if self._max_concurrent <= floor:
            if active_count > 1:
                self.notify(
                    f"Cannot lower slots below {active_count} active recording(s).",
                    severity="warning",
                )
            return
        self._max_concurrent -= 1
        if self._watcher:
            self._call_watcher(self._watcher.set_max_concurrent, self._max_concurrent)
        self._refresh_telemetry()
        self.notify(f"Max concurrent recordings set to {self._max_concurrent}")

    def action_slots_up(self) -> None:
        if self._is_input_open:
            return
        self._max_concurrent += 1
        if self._watcher:
            self._call_watcher(self._watcher.set_max_concurrent, self._max_concurrent)
        self._refresh_telemetry()
        self.notify(f"Max concurrent recordings set to {self._max_concurrent}")

    def _sync_chat_button(self) -> None:
        btn = self.query_one("#btn_toggle_chat", Button)
        if self._site_label != "Fansly":
            btn.label = "Chat: N/A"
            btn.disabled = True
        elif self._chat_enabled:
            btn.label = "Chat: ON (c)"
            btn.variant = "success"
        else:
            btn.label = "Chat: OFF (c)"
            btn.variant = "default"

    def action_toggle_chat(self) -> None:
        if self._is_input_open:
            return
        if self._site_label != "Fansly":
            self.notify(
                "Live chat capture is only available on Fansly.", severity="warning"
            )
            return
        self._chat_enabled = not self._chat_enabled
        if self._watcher:
            self._call_watcher(self._watcher.set_chat_enabled, self._chat_enabled)
        self._sync_chat_button()
        self._refresh_telemetry()
        msg = (
            "enabled (applies to new stream starts)"
            if self._chat_enabled
            else "disabled"
        )
        self.notify(f"Fansly live chat {msg}.")

    def _open_entry_folder(self, entry: StreamRowState | None) -> None:
        import ofscraper.classes.table.utils.open_folder as open_folder

        try:
            target = _resolve_entry_target(entry)
            open_folder.open_target(target)
            self.notify(f"Opened: {target.folder}", title="Open Folder", markup=False)
        except Exception as e:
            folder = getattr(locals().get("target"), "folder", None)
            if isinstance(e, open_folder.OpenError) and folder is not None and _open_in_vscode(folder):
                self.notify(
                    f"Opened in VS Code: {folder}",
                    title="Open Folder",
                    markup=False,
                )
                return
            suffix = f" ({folder})" if folder is not None else ""
            self.notify(
                f"{e}{suffix}",
                title="Open Folder",
                severity="warning",
                markup=False,
            )

    def action_open_folder(self) -> None:
        if self._is_input_open:
            return
        self._open_entry_folder(self._selected_entry())

    def _sync_filter_button(self) -> None:
        labels = {
            "all": ("Filter: All (f)", "default"),
            "online": ("Filter: Online (f)", "success"),
            "recording": ("Filter: Rec (f)", "primary"),
        }
        label, variant = labels.get(self._filter_mode, ("Filter: Online (f)", "success"))
        btn = self.query_one("#btn_filter_active", Button)
        btn.label = label
        btn.variant = variant

    def action_toggle_active_only(self) -> None:
        if self._is_input_open:
            return
        order = ("online", "recording", "all")
        cur = self._filter_mode if self._filter_mode in order else "online"
        self._filter_mode = order[(order.index(cur) + 1) % len(order)]
        self._sync_filter_button()
        self._rebuild_table()
        shown = len(self._shown_keys)
        total = len(self._streams)
        if total > 0 and shown == 0:
            search_note = f" + search '{self._search_query}'" if self._search_query else ""
            self.notify(
                f"Showing 0 of {total} creator(s) under '{self._filter_mode}' filter{search_note} (press f to cycle).",
                severity="information",
            )

    def action_clear_ended(self) -> None:
        if self._is_input_open:
            return
        if not self._store.clear_ended():
            return
        self._rebuild_table()
        self._refresh_telemetry()

    def action_abort_tui(self) -> None:
        self._user_aborted = True
        self.action_quit_tui()

    def action_quit_tui(self) -> None:
        if self._is_input_open:
            self._hide_add_user()
            self._hide_search_bar()
            return
        if self._live_thread is None or self._live_thread.finished.is_set():
            self.exit(self._user_aborted)
            return
        if self._stopping:
            self._user_aborted = True
            self._live_thread.force_stop()
            self.exit(True)
            return

        self._stopping = True
        if not self.watch:
            self._user_aborted = True
        self._refresh_telemetry()
        self.notify(
            "Finalizing active recordings cleanly... Press Ctrl+X or q again to force quit.",
            severity="warning",
        )

        def _stopper():
            self._live_thread.stop(timeout=30)
            self._ui_dispatch(self.exit, self._user_aborted)

        threading.Thread(target=_stopper, daemon=True, name="live-tui-stop").start()


def run_live_tui(watch: bool, runner=None, menu: bool = False) -> bool:
    """Launch the interactive Live Stream TUI around LiveThread."""
    import ofscraper.sites as sites

    if runner is None and not sites.is_fansly():
        from ofscraper.sites.onlyfans import live_capture

        if not live_capture.playwright_ready():
            return False

    import ofscraper.utils.console as console_

    shared_console = console_.get_shared_console()
    was_quiet = shared_console.quiet
    app = LiveStreamApp(watch=watch, runner=runner)
    aborted = False
    try:
        aborted = bool(app.run())
    finally:
        if app._live_thread and app._live_thread.is_alive():
            app._live_thread.stop(timeout=15)
        shared_console.quiet = was_quiet

    if aborted and not watch:
        if menu:
            return True
        raise SystemExit(130)
    return bool(menu)
