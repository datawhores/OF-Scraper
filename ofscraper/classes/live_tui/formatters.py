import datetime
import math

from rich.markup import escape as rich_escape
from rich.text import Text

from ofscraper.classes.live_tui.state import (
    RESUMABLE_STATUSES,
    STOPPABLE_STATUSES,
    StreamRowState,
)
from ofscraper.sites.fansly.live import utc_start

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


def _status_order(status: str) -> int:
    return STATUS_ORDER.get(status, 99)


def _epoch_seconds(started_at) -> float | None:
    if started_at is None or started_at == "":
        return None
    if isinstance(started_at, datetime.datetime):
        return utc_start(started_at).timestamp()
    try:
        val = float(started_at)
    except (TypeError, ValueError):
        try:
            return datetime.datetime.fromisoformat(str(started_at)).timestamp()
        except ValueError:
            return None
    if not math.isfinite(val) or val <= 0:
        return None
    return val / 1000.0 if val > 1e10 else val


def sort_key_for_entry(entry: StreamRowState, sort_key: str, now_wall: float):
    if sort_key == "status":
        return (_status_order(entry.status), -entry.updated_at, entry.username.lower())
    if sort_key == "username":
        return entry.username.lower()
    if sort_key == "site":
        return entry.site.lower()
    if sort_key == "uptime":
        anchor = entry.started_epoch or entry.first_seen
        return (entry.ended_at or now_wall) - anchor
    if sort_key == "saved":
        return entry.total_bytes
    if sort_key == "speed":
        return entry.speed_bps
    if sort_key == "parts":
        return entry.part_num
    if sort_key == "chat":
        return entry.chat_count
    return (entry.title or entry.reason).lower()


def format_cells(
    entry: StreamRowState, now_wall: float, *, chat_enabled: bool
) -> dict[str, Text]:
    badge, badge_style = STATUS_STYLE.get(
        entry.status, (entry.status.upper(), "bold white")
    )
    speed_txt = (
        f"{_fmt_bytes(entry.speed_bps)}/s"
        if entry.status == "recording" and entry.speed_bps > 0
        else "—"
    )

    if entry.status in STOPPABLE_STATUSES:
        toggle_cell = Text("[Stop]", style="bold bright_yellow")
    elif entry.status in RESUMABLE_STATUSES:
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
        chat_txt = "0 msg" if chat_enabled else "—"

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
        "uptime": Text(
            entry.uptime_str(now_wall)
            if entry.is_online or entry.total_bytes > 0
            else "—",
            style="bold bright_white",
        ),
        "saved": Text(
            _fmt_bytes(entry.total_bytes) if entry.total_bytes > 0 else "0 B",
            style="bold bright_green",
        ),
        "speed": Text(
            speed_txt, style="bold gold1" if speed_txt != "—" else "dim white"
        ),
        "parts": Text(
            parts_txt, style="bold plum1" if parts_txt != "—" else "dim white"
        ),
        "chat": Text(
            chat_txt, style="bold cyan" if entry.chat_count > 0 else "dim white"
        ),
        "detail": Text(detail_txt, style="dark_sea_green1"),
    }


def format_telemetry(
    *,
    site_label: str,
    watch: bool,
    interval: int,
    chat_enabled: bool,
    poll_count: int,
    recording: int,
    max_concurrent: int,
    online_cnt: int,
    queued: int,
    stopping: bool,
    poll_state: str,
    paused: bool,
    next_poll_deadline: float | None,
    last_error: str | None,
    total_bytes: int,
    total_speed: float,
    now_mono: float,
) -> tuple[str, str, str]:
    mode_str = f"Watch ({interval}s)" if watch else "One-Shot (--live)"
    chat_str = "ON" if chat_enabled else ("N/A" if site_label == "OnlyFans" else "OFF")

    if stopping:
        poll_badge = "[bold bright_yellow]Stopping recordings cleanly...[/bold bright_yellow]"
    elif poll_state == "finished":
        poll_badge = "[bold bright_green]Session Finished (press q to close)[/bold bright_green]"
    elif poll_state == "polling":
        poll_badge = "[bold bright_cyan]Checking live creators now...[/bold bright_cyan]"
    elif paused or poll_state == "paused":
        poll_badge = "[bold bright_yellow]Paused (Space to resume)[/bold bright_yellow]"
    elif next_poll_deadline is not None:
        rem = max(0, int(round(next_poll_deadline - now_mono)))
        poll_badge = f"Next check in [bold bright_cyan]{rem}s[/bold bright_cyan]"
    else:
        poll_badge = f"[dim]{poll_state}[/dim]"

    err_line = (
        f"\n[bold red]Last Error:[/bold red] {rich_escape(last_error[:45])}"
        if last_error
        else ""
    )

    left = (
        f"[bold ansi_blue]Site:[/bold ansi_blue] {site_label}   "
        f"[bold ansi_blue]Mode:[/bold ansi_blue] {mode_str}\n"
        f"[bold ansi_blue]Chat:[/bold ansi_blue] {chat_str}   "
        f"[bold ansi_blue]Checks:[/bold ansi_blue] {poll_count}"
    )
    mid = (
        f"[bold ansi_blue]Slots:[/bold ansi_blue] [bold bright_green]{recording}[/bold bright_green] / {max_concurrent} active  "
        f"| Online: [bold medium_spring_green]{online_cnt}[/bold medium_spring_green]  | Queued: {queued}\n"
        f"[bold ansi_blue]Poll:[/bold ansi_blue]  {poll_badge}{err_line}"
    )
    right = (
        f"[bold ansi_blue]Saved:[/bold ansi_blue] [bold bright_green]{_fmt_bytes(total_bytes)}[/bold bright_green]\n"
        f"[bold ansi_blue]Speed:[/bold ansi_blue] [bold gold1]{_fmt_bytes(total_speed)}/s[/bold gold1]"
    )
    return left, mid, right
