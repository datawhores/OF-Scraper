from collections import deque
import contextlib
import datetime
import logging
import pathlib
import re
import threading
import time
from dataclasses import dataclass, field

from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.widgets import Button, Input, RichLog, Static

import ofscraper.utils.events as of_events
from ofscraper.classes.live_tui.compose import compose_live_tui
from ofscraper.classes.live_tui.css import LIVE_CSS
from ofscraper.classes.table.sections.table import DataTableExtended

log = logging.getLogger("shared")

RECORDING_STATUSES = {"recording", "joining", "retrying", "remuxing", "stopping"}
ONLINE_STATUSES = {"recording", "joining", "retrying", "remuxing", "stopping", "queued", "online", "stopped"}

STATUS_ORDER = {
    "recording": 0,
    "retrying": 1,
    "joining": 2,
    "remuxing": 3,
    "stopping": 4,
    "queued": 5,
    "online": 5,
    "stopped": 6,
    "failed": 7,
    "ended": 8,
    "offline": 9,
}

STATUS_STYLE = {
    "recording": ("RECORDING", "bold bright_green"),
    "joining": ("JOINING", "bold cyan"),
    "retrying": ("RETRYING", "bold bright_yellow"),
    "remuxing": ("REMUXING", "bold deep_sky_blue1"),
    "stopping": ("STOPPING...", "bold orange1"),
    "queued": ("QUEUED", "bold gold1"),
    "online": ("ONLINE", "bold medium_spring_green"),
    "stopped": ("STOPPED (LIVE)", "bold violet"),
    "ended": ("ENDED", "dim white"),
    "failed": ("FAILED", "bold red"),
    "offline": ("OFFLINE", "dim white"),
}

# Action buttons come first on every row for instant one-click access
COLUMNS = (
    ("username", "Creator", 20),
    ("act_toggle", "Rec", 11),
    ("act_remove", "Remove", 10),
    ("act_folder", "Folder", 10),
    ("status", "Status", 16),
    ("site", "Site", 10),
    ("uptime", "Uptime", 11),
    ("saved", "Saved", 12),
    ("speed", "Speed", 12),
    ("parts", "Parts", 10),
    ("chat", "Chat", 10),
    ("detail", "Title / Status Detail", 44),
)


def _fmt_bytes(num_bytes: float) -> str:
    val = float(max(0.0, num_bytes))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if val < 1024.0 or unit == "TB":
            return f"{int(val)} B" if unit == "B" else f"{val:.1f} {unit}"
        val /= 1024.0
    return "0 B"


def _fmt_hms(seconds: float) -> str:
    sec = max(0, int(seconds))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def _epoch_seconds(started_at) -> float | None:
    if started_at is None:
        return None
    if isinstance(started_at, (int, float)):
        val = float(started_at)
        return val / 1000.0 if val > 1e10 else val
    try:
        val = float(str(started_at))
        return val / 1000.0 if val > 1e10 else val
    except ValueError:
        try:
            return datetime.datetime.fromisoformat(str(started_at)).timestamp()
        except ValueError:
            return None


@dataclass
class StreamRowState:
    key: str
    site: str
    account_id: str
    username: str
    status: str = "offline"
    is_online: bool = False
    user_stopped: bool = False
    title: str = ""
    reason: str = ""
    started_epoch: float | None = None
    first_seen: float = field(default_factory=time.time)
    ended_at: float | None = None
    part_paths: list[pathlib.Path] = field(default_factory=list)
    part_num: int = 0
    chat_count: int = 0
    total_bytes: int = 0
    prev_bytes: int = 0
    prev_sample_mono: float = 0.0
    speed_bps: float = 0.0
    updated_at: float = field(default_factory=time.monotonic)

    def add_part(self, path: pathlib.Path | None, part_num: int | None = None):
        if path is not None:
            p = pathlib.Path(path)
            if p not in self.part_paths:
                self.part_paths.append(p)
        if part_num:
            self.part_num = max(self.part_num, int(part_num))
        elif self.part_paths:
            self.part_num = max(self.part_num, len(self.part_paths))

    def refresh_disk_metrics(self, now_mono: float):
        if not self.part_paths:
            return
        total = 0
        for p in self.part_paths:
            try:
                if p.exists():
                    total += p.stat().st_size
            except OSError:
                pass
        if self.prev_sample_mono > 0 and self.status == "recording":
            dt = now_mono - self.prev_sample_mono
            if dt >= 0.25:
                delta = max(0, total - self.prev_bytes)
                instant = delta / dt
                self.speed_bps = (
                    instant
                    if self.speed_bps <= 0
                    else (0.6 * instant + 0.4 * self.speed_bps)
                )
                self.prev_bytes = total
                self.prev_sample_mono = now_mono
        else:
            self.speed_bps = 0.0
            self.prev_bytes = total
            self.prev_sample_mono = now_mono
        self.total_bytes = max(self.total_bytes, total)

    def latest_existing_file(self) -> pathlib.Path | None:
        for p in reversed(self.part_paths):
            try:
                if p.is_file():
                    return p
            except OSError:
                continue
        return None

    def uptime_str(self, now_wall: float) -> str:
        anchor = self.started_epoch or self.first_seen
        end = self.ended_at if self.status in {"ended", "failed"} and self.ended_at else now_wall
        return _fmt_hms(end - anchor)


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

        self._streams: dict[str, StreamRowState] = {}
        self._username_index: dict[tuple[str, str], str] = {}
        self._chat_buffers: dict[str, deque[Text]] = {}
        self._active_chat_user: str | None = None
        self._shown_keys: set[str] = set()
        self._filter_mode = "online"
        self._sort_key = "status"
        self._sort_reverse = False

        self._stopping = False
        self._user_aborted = False

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
            return not self.query_one("#add_user_bar").has_class("-hidden")
        except Exception:
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
                self._site_label = "Fansly" if str(kw["site"]).lower() == "fansly" else "OnlyFans"
            self._max_concurrent = int(kw.get("max_concurrent") or self._max_concurrent)
            self._interval = int(kw.get("interval") or self._interval)
            if self._watcher is not None:
                self._include_following = bool(getattr(self._watcher, "include_following", self._include_following))
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
            for t in kw.get("targets") or ():
                raw_id = t.get("accountId")
                uname = str(t.get("username") or raw_id or "unknown")
                row_key = f"{site}:{raw_id}" if raw_id is not None else f"{site}:{uname.lower()}"
                self._username_index[(site, uname.lower())] = row_key
                if row_key not in self._streams:
                    self._streams[row_key] = StreamRowState(
                        key=row_key,
                        site="Fansly" if site == "fansly" else "OnlyFans",
                        account_id=str(raw_id if raw_id is not None else uname),
                        username=uname,
                        status="offline",
                        is_online=False,
                        reason="Watched (offline)",
                    )
            self._rebuild_table()
        elif state == "ok":
            self._poll_count += 1
            self._poll_state = "idle"
            self._last_error = None
            site = str(kw.get("site") or self._site_label).lower()
            online_list = kw.get("online") or []
            online_keys = set()
            for s in online_list:
                raw_id = s.get("accountId")
                uname = str(s.get("username") or raw_id or "unknown")
                row_key = f"{site}:{raw_id}" if raw_id is not None else f"{site}:{uname.lower()}"
                self._username_index[(site, uname.lower())] = row_key
                online_keys.add(row_key)
                entry = self._streams.get(row_key)
                if entry is None:
                    entry = StreamRowState(
                        key=row_key,
                        site="Fansly" if site == "fansly" else "OnlyFans",
                        account_id=str(raw_id if raw_id is not None else uname),
                        username=uname,
                        status="online",
                        is_online=True,
                        title=str(s.get("title") or ""),
                        started_epoch=_epoch_seconds(s.get("startedAt")),
                        reason="Live now",
                    )
                    self._streams[row_key] = entry
                else:
                    entry.is_online = True
                    if s.get("title"):
                        entry.title = str(s["title"])
                    if entry.user_stopped:
                        entry.status = "stopped"
                        entry.reason = "Stopped by user (click [Resume] or press r)"
                    elif entry.status in {"offline", "ended", "failed"}:
                        entry.status = "online"
                        entry.reason = "Live now"
            for row_key, entry in self._streams.items():
                if row_key.startswith(f"{site}:") and row_key not in online_keys:
                    entry.is_online = False
                    entry.user_stopped = False
                    if entry.status in {"online", "queued", "stopped"}:
                        entry.status = "offline"
                        entry.reason = "Offline"
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
            self._next_poll_deadline = None if self._paused else (time.monotonic() + timeout)
        self._refresh_telemetry()

    def _handle_stream(self, kw: dict):
        site = str(kw.get("site") or self._site_label).lower()
        username = str(kw.get("username") or "unknown")
        raw_id = kw.get("account_id")
        lookup = (site, username.lower())

        if raw_id is not None:
            row_key = f"{site}:{raw_id}"
            self._username_index[lookup] = row_key
        else:
            row_key = self._username_index.get(lookup) or f"{site}:{username.lower()}"
            self._username_index[lookup] = row_key

        entry = self._streams.get(row_key)
        was_status = entry.status if entry else None
        if entry is None:
            entry = StreamRowState(
                key=row_key,
                site="Fansly" if site == "fansly" else "OnlyFans",
                account_id=str(raw_id if raw_id is not None else username),
                username=username,
            )
            self._streams[row_key] = entry
        elif raw_id is not None:
            entry.account_id = str(raw_id)

        new_status = str(kw.get("status") or entry.status).lower()
        # Ignore a late "ended" or "stopped" from an exiting recorder when user already clicked Resume ("queued")
        if entry.status == "queued" and not entry.user_stopped and new_status in {"stopped", "ended"}:
            return
        if entry.user_stopped and new_status == "ended":
            new_status = "stopped"
        if was_status in {"ended", "failed", "offline", "stopped"} and new_status in {"queued", "joining", "recording", "online"}:
            entry.ended_at = None
            entry.first_seen = time.time()

        entry.status = new_status
        if new_status in ONLINE_STATUSES:
            entry.is_online = True
        elif new_status in {"ended", "failed", "offline"}:
            entry.is_online = False

        if kw.get("title"):
            entry.title = str(kw["title"])
        if kw.get("reason") is not None:
            entry.reason = str(kw["reason"])
        started_ep = _epoch_seconds(kw.get("started_at"))
        if started_ep is not None:
            entry.started_epoch = started_ep
        entry.add_part(kw.get("part_path"), kw.get("part_num"))
        entry.updated_at = time.monotonic()

        if new_status in {"ended", "failed", "stopped"}:
            entry.refresh_disk_metrics(time.monotonic())
            entry.speed_bps = 0.0
            if new_status in {"ended", "failed"} and entry.ended_at is None:
                entry.ended_at = time.time()

        if was_status != new_status and self._sort_key == "status":
            self._rebuild_table()
        else:
            self._upsert_row(entry)
        self._refresh_telemetry()

    def _handle_chat(self, kw: dict):
        username = str(kw.get("username") or "").strip()
        sender = str(kw.get("sender") or "user")
        content = str(kw.get("content") or "").strip()
        total = kw.get("total_received")
        ukey = username.lower()

        row_key = self._username_index.get(("fansly", ukey))
        if row_key and row_key in self._streams:
            entry = self._streams[row_key]
            entry.chat_count = int(total) if total is not None else (entry.chat_count + 1)
            self._upsert_row(entry)

        if content:
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            line = Text()
            line.append(f"[{stamp}] ", style="dim")
            line.append(f"{sender}: ", style="bold bright_green" if sender != "system" else "bold cyan")
            line.append(content)

            buf = self._chat_buffers.setdefault(ukey, deque(maxlen=500))
            buf.append(line)

            selected = self._selected_entry()
            target_user = selected.username.lower() if selected else None
            if self._active_chat_user != target_user:
                self._sync_chat_pane(force=True)
            elif target_user == ukey or target_user is None:
                if target_user is None and username:
                    line_all = Text()
                    line_all.append(f"[{stamp}] ", style="dim")
                    line_all.append(f"@{username} ", style="bold cyan")
                    line_all.append(f"{sender}: ", style="bold bright_green")
                    line_all.append(content)
                    self.query_one("#live_chat_log", RichLog).write(line_all, scroll_end=True)
                else:
                    self.query_one("#live_chat_log", RichLog).write(line, scroll_end=True)
                    self._update_chat_title(selected)

    def _update_chat_title(self, entry: StreamRowState | None) -> None:
        title_widget = self.query_one("#chat_pane_title", Static)
        if entry is None:
            title_widget.update("Fansly Live Chat (--live-chat)")
        elif entry.site != "Fansly":
            title_widget.update(f"Live Chat — @{entry.username} (Fansly only)")
        else:
            title_widget.update(f"Fansly Live Chat — @{entry.username} ({entry.chat_count} msg)")

    def _sync_chat_pane(self, force: bool = False) -> None:
        entry = self._selected_entry()
        target_user = entry.username.lower() if entry else None
        if not force and target_user == self._active_chat_user:
            self._update_chat_title(entry)
            return
        self._active_chat_user = target_user
        self._update_chat_title(entry)
        chat_widget = self.query_one("#live_chat_log", RichLog)
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

    def _visible_entries(self) -> list[StreamRowState]:
        rows = list(self._streams.values())
        if self._filter_mode == "online":
            rows = [r for r in rows if r.is_online or r.status in ONLINE_STATUSES]
        elif self._filter_mode == "recording":
            rows = [r for r in rows if r.status in RECORDING_STATUSES]

        def sort_fn(r: StreamRowState):
            if self._sort_key == "status":
                return (STATUS_ORDER.get(r.status, 99), -r.updated_at, r.username.lower())
            if self._sort_key == "username":
                return r.username.lower()
            if self._sort_key == "site":
                return r.site.lower()
            if self._sort_key == "uptime":
                anchor = r.started_epoch or r.first_seen
                return (r.ended_at or time.time()) - anchor
            if self._sort_key == "saved":
                return r.total_bytes
            if self._sort_key == "speed":
                return r.speed_bps
            if self._sort_key == "parts":
                return r.part_num
            if self._sort_key == "chat":
                return r.chat_count
            return (r.title or r.reason).lower()

        rows.sort(key=sort_fn, reverse=self._sort_reverse)
        return rows

    def _format_cells(self, entry: StreamRowState, now_wall: float) -> dict[str, Text]:
        badge, badge_style = STATUS_STYLE.get(entry.status, (entry.status.upper(), "bold white"))
        speed_txt = f"{_fmt_bytes(entry.speed_bps)}/s" if entry.status == "recording" and entry.speed_bps > 0 else "—"

        if entry.status in {"recording", "joining", "retrying", "queued", "online"}:
            toggle_cell = Text("[Stop]", style="bold bright_yellow")
        elif entry.status in {"stopped", "stopping"}:
            toggle_cell = Text("[Resume]", style="bold bright_green")
        else:
            toggle_cell = Text("—", style="dim white")

        if entry.part_num > 0:
            parts_txt = f"Part {entry.part_num}" if entry.site == "Fansly" else "1 file"
        else:
            parts_txt = "—"

        if entry.site != "Fansly":
            chat_txt = "N/A"
        elif entry.chat_count > 0:
            chat_txt = f"{entry.chat_count} msg"
        else:
            chat_txt = "0 msg" if self._chat_enabled else "—"

        if entry.title and entry.reason:
            detail_txt = f"{entry.title} — {entry.reason}"
        else:
            detail_txt = entry.title or entry.reason or "—"

        return {
            "act_toggle": toggle_cell,
            "act_remove": Text("[Remove]", style="bold red"),
            "act_folder": Text("[Folder]", style="bold cyan"),
            "status": Text(f"[{badge}]", style=badge_style),
            "username": Text(entry.username, style="bold medium_spring_green"),
            "site": Text(entry.site, style="bold deep_sky_blue1"),
            "uptime": Text(entry.uptime_str(now_wall) if entry.is_online or entry.total_bytes > 0 else "—", style="bold bright_white"),
            "saved": Text(_fmt_bytes(entry.total_bytes) if entry.total_bytes > 0 else "0 B", style="bold bright_green"),
            "speed": Text(speed_txt, style="bold gold1" if speed_txt != "—" else "dim white"),
            "parts": Text(parts_txt, style="bold plum1" if parts_txt != "—" else "dim white"),
            "chat": Text(chat_txt, style="bold cyan" if entry.chat_count > 0 else "dim white"),
            "detail": Text(detail_txt, style="dark_sea_green1"),
        }

    def _upsert_row(self, entry: StreamRowState):
        table = self.query_one("#streams_table", DataTableExtended)
        should_show = (
            self._filter_mode == "all"
            or (self._filter_mode == "online" and (entry.is_online or entry.status in ONLINE_STATUSES))
            or (self._filter_mode == "recording" and entry.status in RECORDING_STATUSES)
        )
        if not should_show:
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
        for idx, entry in enumerate(self._visible_entries()):
            cells = self._format_cells(entry, now_wall)
            table.add_row(*(cells[col] for col, _, _ in COLUMNS), key=entry.key)
            self._shown_keys.add(entry.key)
            if entry.key == selected_key:
                restore_idx = idx
        if restore_idx is not None:
            with contextlib.suppress(Exception):
                table.move_cursor(row=restore_idx, column=prev_col)
        self._sync_chat_pane()

    def _on_tick(self):
        now_mono = time.monotonic()
        now_wall = time.time()
        table = self.query_one("#streams_table", DataTableExtended)

        for entry in self._streams.values():
            if entry.status in {"recording", "joining", "retrying", "remuxing", "queued", "stopped"}:
                entry.refresh_disk_metrics(now_mono)
                if entry.key in self._shown_keys:
                    cells = self._format_cells(entry, now_wall)
                    for col in ("uptime", "saved", "speed", "parts", "chat"):
                        table.update_cell_at_key(entry.key, col, cells[col])

        if self._live_thread and self._live_thread.finished.is_set() and self._poll_state != "finished":
            self._poll_state = "finished"

        self._refresh_telemetry()

    def _refresh_telemetry(self):
        recording = sum(1 for e in self._streams.values() if e.status in RECORDING_STATUSES)
        online_cnt = sum(1 for e in self._streams.values() if e.is_online or e.status in ONLINE_STATUSES)
        queued = sum(1 for e in self._streams.values() if e.status == "queued")
        total_bytes = sum(e.total_bytes for e in self._streams.values())
        total_speed = sum(e.speed_bps for e in self._streams.values() if e.status == "recording")

        mode_str = f"Watch ({self._interval}s)" if self.watch else "One-Shot (--live)"
        chat_str = "ON" if self._chat_enabled else ("N/A" if self._site_label == "OnlyFans" else "OFF")

        if self._stopping:
            poll_badge = "[bold bright_yellow]Stopping recordings cleanly...[/bold bright_yellow]"
        elif self._poll_state == "finished":
            poll_badge = "[bold bright_green]Session Finished (press q to close)[/bold bright_green]"
        elif self._poll_state == "polling":
            poll_badge = "[bold bright_cyan]Checking live creators now...[/bold bright_cyan]"
        elif self._paused or self._poll_state == "paused":
            poll_badge = "[bold bright_yellow]Paused (Space to resume)[/bold bright_yellow]"
        elif self._next_poll_deadline is not None:
            rem = max(0, int(round(self._next_poll_deadline - time.monotonic())))
            poll_badge = f"Next check in [bold bright_cyan]{rem}s[/bold bright_cyan]"
        else:
            poll_badge = f"[dim]{self._poll_state}[/dim]"

        err_line = f"\n[bold red]Last Error:[/bold red] {self._last_error[:45]}" if self._last_error else ""

        self.query_one("#telemetry_left", Static).update(
            f"[bold ansi_blue]Site:[/bold ansi_blue] {self._site_label}   "
            f"[bold ansi_blue]Mode:[/bold ansi_blue] {mode_str}\n"
            f"[bold ansi_blue]Chat:[/bold ansi_blue] {chat_str}   "
            f"[bold ansi_blue]Checks:[/bold ansi_blue] {self._poll_count}"
        )
        self.query_one("#telemetry_mid", Static).update(
            f"[bold ansi_blue]Slots:[/bold ansi_blue] [bold bright_green]{recording}[/bold bright_green] / {self._max_concurrent} active  "
            f"| Online: [bold medium_spring_green]{online_cnt}[/bold medium_spring_green]  | Queued: {queued}\n"
            f"[bold ansi_blue]Poll:[/bold ansi_blue]  {poll_badge}{err_line}"
        )
        self.query_one("#telemetry_right", Static).update(
            f"[bold ansi_blue]Saved:[/bold ansi_blue] [bold bright_green]{_fmt_bytes(total_bytes)}[/bold bright_green]\n"
            f"[bold ansi_blue]Speed:[/bold ansi_blue] [bold gold1]{_fmt_bytes(total_speed)}/s[/bold gold1]"
        )

    # ------------------------------------------------------------------ user actions

    def _selected_row_key(self) -> str | None:
        table = self.query_one("#streams_table", DataTableExtended)
        if table.row_count == 0:
            return None
        try:
            return table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0)).row_key.value
        except Exception:
            return None

    def _selected_entry(self) -> StreamRowState | None:
        key = self._selected_row_key()
        return self._streams.get(key) if key else None

    def on_data_table_header_selected(self, event) -> None:
        col_key = getattr(getattr(event, "column_key", None), "value", None)
        if not col_key or col_key.startswith("act_"):
            return
        if self._sort_key == col_key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_key = col_key
            self._sort_reverse = col_key in {"saved", "speed", "uptime", "parts", "chat"}
        self._rebuild_table()

    def on_data_table_cell_highlighted(self, event) -> None:
        self._sync_chat_pane()

    def on_data_table_row_highlighted(self, event) -> None:
        self._sync_chat_pane()

    def on_data_table_cell_selected(self, event) -> None:
        table = event.control
        col_key = table.ordered_columns_keys[event.coordinate.column]
        row_key = event.cell_key.row_key.value
        entry = self._streams.get(row_key)
        if entry is None:
            return
        if col_key == "act_toggle":
            if entry.status in {"recording", "joining", "retrying", "queued", "online"}:
                self._stop_entry(entry)
            elif entry.status in {"stopped", "stopping"}:
                self._resume_entry(entry)
        elif col_key == "act_remove":
            self._remove_entry(entry)
        elif col_key == "act_folder":
            self._open_entry_folder(entry)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "add_user_input":
            self._submit_add_user()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        dispatch = {
            "btn_poll": self.action_poll_now,
            "btn_toggle_following": self.action_toggle_following,
            "btn_show_add_user": self.action_show_add_user,
            "btn_submit_add_user": self._submit_add_user,
            "btn_cancel_add_user": self._hide_add_user,
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
        scope = "followed creators" if self._site_label == "Fansly" else "active subscriptions"
        if not self._include_following:
            extra = getattr(self._watcher, "extra_usernames", set())
            to_drop = [
                k for k, v in self._streams.items()
                if v.status == "offline" and v.username.lower() not in extra
            ]
            for k in to_drop:
                self._streams.pop(k, None)
            self._rebuild_table()
            self.notify(f"Excluded {scope}; tracking explicit usernames only.")
        else:
            self.notify(f"Included all {scope}; polling now...")

    def action_show_add_user(self) -> None:
        bar = self.query_one("#add_user_bar")
        bar.remove_class("-hidden")
        inp = self.query_one("#add_user_input", Input)
        inp.value = ""
        self.set_focus(inp)

    def _hide_add_user(self) -> None:
        self.query_one("#add_user_bar").add_class("-hidden")
        self.set_focus(self.query_one("#streams_table"))

    def _submit_add_user(self) -> None:
        inp = self.query_one("#add_user_input", Input)
        raw = inp.value.strip()
        self._hide_add_user()
        if not raw:
            return
        names = [part.lstrip("@").strip() for part in re.split(r"[,\s]+", raw) if part.lstrip("@").strip()]
        if not names:
            return
        if not self._watcher:
            self.notify("Watcher is not active right now.", severity="warning")
            return
        self._call_watcher(self._watcher.add_usernames, names)
        self.notify(f"Added {', '.join(names)} to live watchlist; checking now...", markup=False)

    def _remove_entry(self, entry: StreamRowState) -> None:
        if not self._watcher:
            self.notify("Watcher has already finished.", severity="warning")
            return
        self._call_watcher(self._watcher.remove_username, entry.username, entry.account_id)
        self._streams.pop(entry.key, None)
        self._username_index = {
            uk: rk for uk, rk in self._username_index.items() if rk in self._streams
        }
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
        if entry.status in {"recording", "joining", "retrying", "queued", "online"}:
            entry.user_stopped = True
            was_rec = entry.status in {"recording", "joining", "retrying"}
            entry.status = "stopping" if was_rec else "stopped"
            entry.reason = "Finalizing MP4 cleanly..." if was_rec else "Stopped by user (click [Resume] or press r)"
            self._upsert_row(entry)
            self._call_watcher(self._watcher.stop_creator, entry.account_id)
            self.notify(f"Stopping {entry.username}...", markup=False)
        else:
            self.notify(f"{entry.username} is not currently active.", markup=False)

    def _resume_entry(self, entry: StreamRowState) -> None:
        if not self._watcher:
            self.notify("Watcher has already finished.", severity="warning")
            return
        if entry.status in {"stopped", "stopping"}:
            entry.user_stopped = False
            entry.status = "queued"
            entry.reason = "Resuming stream..."
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
        active_entries = [
            e for e in self._streams.values()
            if e.status in {"recording", "joining", "retrying", "queued", "online"}
        ]
        ids = [e.account_id for e in active_entries]
        self._call_watcher(self._watcher.stop_all, ids)
        for e in active_entries:
            e.status = "stopped"
            e.reason = "Stopped all by user (press a to start all)"
        self._rebuild_table()
        self._refresh_telemetry()
        self.notify(f"Stopping {len(active_entries)} active/online stream(s)...")

    def action_start_all(self) -> None:
        if self._is_input_open:
            return
        if not self._watcher:
            self.notify("Watcher has already finished.", severity="warning")
            return
        stopped_entries = [e for e in self._streams.values() if e.status in {"stopped", "stopping"}]
        self._call_watcher(self._watcher.resume_all)
        for e in stopped_entries:
            e.status = "queued"
            e.reason = "Resuming on immediate check..."
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
        active_count = sum(
            1 for e in self._streams.values() if e.status in RECORDING_STATUSES
        )
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

    def action_toggle_online_only(self) -> None:
        if self._is_input_open:
            return
        self._online_only = not self._online_only
        mode = "Online / Active Only" if self._online_only else "All Seen Creators"
        self.notify(f"Filter: {mode}")
        if hasattr(self, "_rebuild_table"):
            self._rebuild_table()

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
            self.notify("Live chat capture is only available on Fansly.", severity="warning")
            return
        self._chat_enabled = not self._chat_enabled
        if self._watcher:
            self._call_watcher(self._watcher.set_chat_enabled, self._chat_enabled)
        self._sync_chat_button()
        self._refresh_telemetry()
        msg = "enabled (applies to new stream starts)" if self._chat_enabled else "disabled"
        self.notify(f"Fansly live chat {msg}.")

    def _open_entry_folder(self, entry: StreamRowState | None) -> None:
        import os
        import shutil
        import subprocess
        import ofscraper.classes.table.utils.open_folder as open_folder
        import ofscraper.sites as sites
        import ofscraper.utils.paths.common as common_paths
        from ofscraper.sites.fansly.live import folder_name

        # VS Code terminals often omit DISPLAY / WAYLAND_DISPLAY / DBUS_SESSION_BUS_ADDRESS
        uid = os.getuid() if hasattr(os, "getuid") else None
        if uid is not None:
            runtime_dir = pathlib.Path(f"/run/user/{uid}")
            if not os.environ.get("WAYLAND_DISPLAY") and runtime_dir.is_dir():
                wl = [w for w in sorted(runtime_dir.glob("wayland-[0-9]*")) if not w.name.endswith(".lock")]
                if wl:
                    os.environ["WAYLAND_DISPLAY"] = wl[0].name
            if not os.environ.get("DBUS_SESSION_BUS_ADDRESS") and (runtime_dir / "bus").exists():
                os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
        if not os.environ.get("DISPLAY"):
            x_socks = sorted(pathlib.Path("/tmp/.X11-unix").glob("X[0-9]*"))
            if x_socks:
                os.environ["DISPLAY"] = f":{x_socks[0].name[1:]}"

        save_root = pathlib.Path(common_paths.get_save_location()).expanduser()
        target = None

        if entry is not None:
            existing = entry.latest_existing_file()
            if existing is not None:
                target = open_folder.Target(open_folder.absolute(existing), select=True)
            else:
                site_dir = "Fansly" if entry.site == "Fansly" else "OnlyFans"
                live_dir = save_root / site_dir / folder_name(entry.username) / "Livestreams"
                creator_dir = live_dir.parent
                site_root = save_root / site_dir
                for candidate in (live_dir, creator_dir, site_root, save_root):
                    if candidate.is_dir():
                        target = open_folder.Target(open_folder.absolute(candidate))
                        break
                if target is None:
                    target = open_folder.Target(open_folder.absolute(live_dir))
        else:
            site_root = save_root / ("Fansly" if sites.is_fansly() else "OnlyFans")
            chosen = site_root if site_root.is_dir() else save_root
            target = open_folder.Target(open_folder.absolute(chosen))

        try:
            open_folder.open_target(target)
            self.notify(f"Opened: {target.folder}", title="Open Folder", markup=False)
        except Exception as e:
            if target.folder.is_dir() and shutil.which("code"):
                try:
                    subprocess.Popen(
                        ["code", "--new-window", str(target.folder)],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    self.notify(f"Opened in VS Code: {target.folder}", title="Open Folder", markup=False)
                    return
                except Exception:
                    pass
            self.notify(f"{e} ({target.folder})", title="Open Folder", severity="warning", markup=False)


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
            self.notify(
                f"Showing 0 of {total} creator(s) under '{self._filter_mode}' filter (press f to cycle).",
                severity="information",
            )

    def action_clear_ended(self) -> None:
        if self._is_input_open:
            return
        to_drop = [k for k, v in self._streams.items() if v.status in {"ended", "failed"}]
        if not to_drop:
            return
        for k in to_drop:
            self._streams.pop(k, None)
        self._username_index = {
            uk: rk for uk, rk in self._username_index.items() if rk in self._streams
        }
        self._rebuild_table()
        self._refresh_telemetry()

    def action_abort_tui(self) -> None:
        self._user_aborted = True
        self.action_quit_tui()

    def action_quit_tui(self) -> None:
        if self._is_input_open:
            self._hide_add_user()
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
    return True if menu else False
