import pathlib
import time
from collections import deque
from dataclasses import dataclass, field

from rich.text import Text

ACTIVE_STATUSES = frozenset({"recording", "joining", "retrying"})
RECORDING_STATUSES = frozenset({"recording", "joining", "retrying", "remuxing", "stopping"})
STOPPABLE_STATUSES = frozenset({"recording", "joining", "retrying", "queued", "online"})
RESUMABLE_STATUSES = frozenset({"stopped", "stopping"})
ONLINE_STATUSES = frozenset(
    {"recording", "joining", "retrying", "remuxing", "stopping", "queued", "online", "stopped"}
)
TICK_STATUSES = frozenset({"recording", "joining", "retrying", "remuxing", "queued", "stopped"})


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

    def add_part(self, path: pathlib.Path | None, part_num: int | None = None) -> None:
        if path is not None:
            p = pathlib.Path(path)
            if p not in self.part_paths:
                self.part_paths.append(p)
        if part_num:
            self.part_num = max(self.part_num, int(part_num))
        elif self.part_paths:
            self.part_num = max(self.part_num, len(self.part_paths))

    def refresh_disk_metrics(self, now_mono: float) -> None:
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
        end = (
            self.ended_at
            if self.status in {"ended", "failed"} and self.ended_at
            else now_wall
        )
        sec = max(0, int(end - anchor))
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}"


def _site_display(site: str) -> str:
    return "Fansly" if site == "fansly" else "OnlyFans"


class LiveStore:
    """Pure-Python state container for LiveStreamApp rows, removals, and chat."""

    def __init__(self) -> None:
        self.streams: dict[str, StreamRowState] = {}
        self.username_index: dict[tuple[str, str], str] = {}
        self.removed_keys: set[str] = set()
        self.removed_user_ids: dict[tuple[str, str], str] = {}
        self.chat_buffers: dict[str, deque[Text]] = {}

    def get(self, row_key: str | None) -> StreamRowState | None:
        return self.streams.get(row_key) if row_key else None

    def prune_username_index(self) -> None:
        self.username_index = {
            uk: rk for uk, rk in self.username_index.items() if rk in self.streams
        }

    def should_show(
        self, entry: StreamRowState, filter_mode: str, search_query: str = ""
    ) -> bool:
        if filter_mode == "all":
            matches_mode = True
        elif filter_mode == "online":
            matches_mode = entry.is_online or entry.status in ONLINE_STATUSES
        elif filter_mode == "recording":
            matches_mode = entry.status in RECORDING_STATUSES
        else:
            return False
        if not matches_mode:
            return False
        if search_query:
            q = search_query.strip().lstrip("@").lower()
            if (
                q
                and q not in entry.username.lower()
                and q not in str(entry.account_id).lower()
            ):
                return False
        return True

    def recording_count(self) -> int:
        return sum(1 for e in self.streams.values() if e.status in RECORDING_STATUSES)

    def telemetry_counts(self) -> tuple[int, int, int, int, float]:
        recording = 0
        online_cnt = 0
        queued = 0
        total_bytes = 0
        total_speed = 0.0
        for e in self.streams.values():
            if e.status in RECORDING_STATUSES:
                recording += 1
            if e.is_online or e.status in ONLINE_STATUSES:
                online_cnt += 1
            if e.status == "queued":
                queued += 1
            total_bytes += e.total_bytes
            if e.status == "recording":
                total_speed += e.speed_bps
        return recording, online_cnt, queued, total_bytes, total_speed

    def apply_targets(self, site: str, targets) -> None:
        for t in targets or ():
            raw_id = t.get("accountId")
            uname = str(t.get("username") or raw_id or "unknown")
            row_key = f"{site}:{raw_id}" if raw_id is not None else f"{site}:{uname.lower()}"
            if row_key in self.removed_keys:
                continue
            self.username_index[(site, uname.lower())] = row_key
            if row_key not in self.streams:
                self.streams[row_key] = StreamRowState(
                    key=row_key,
                    site=_site_display(site),
                    account_id=str(raw_id if raw_id is not None else uname),
                    username=uname,
                    status="offline",
                    is_online=False,
                    reason="Watched (offline)",
                )

    def apply_poll_ok(self, site: str, online_list, parse_epoch=None) -> None:
        if parse_epoch is None:
            from ofscraper.classes.live_tui.formatters import _epoch_seconds

            parse_epoch = _epoch_seconds
        online_keys = set()
        for s in online_list or ():
            raw_id = s.get("accountId")
            uname = str(s.get("username") or raw_id or "unknown")
            row_key = f"{site}:{raw_id}" if raw_id is not None else f"{site}:{uname.lower()}"
            if row_key in self.removed_keys:
                continue
            self.username_index[(site, uname.lower())] = row_key
            online_keys.add(row_key)
            entry = self.streams.get(row_key)
            if entry is None:
                self.streams[row_key] = StreamRowState(
                    key=row_key,
                    site=_site_display(site),
                    account_id=str(raw_id if raw_id is not None else uname),
                    username=uname,
                    status="online",
                    is_online=True,
                    title=str(s.get("title") or ""),
                    started_epoch=parse_epoch(s.get("startedAt")),
                    reason="Live now",
                )
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

        prefix = f"{site}:"
        for row_key, entry in self.streams.items():
            if row_key.startswith(prefix) and row_key not in online_keys:
                entry.is_online = False
                entry.user_stopped = False
                if entry.status in {"online", "queued", "stopped"}:
                    entry.status = "offline"
                    entry.reason = "Offline"

    def apply_stream_event(
        self, site: str, kw: dict, parse_epoch=None
    ) -> tuple[StreamRowState | None, str | None, str | None]:
        if parse_epoch is None:
            from ofscraper.classes.live_tui.formatters import _epoch_seconds

            parse_epoch = _epoch_seconds
        username = str(kw.get("username") or "unknown")
        raw_id = kw.get("account_id")
        lookup = (site, username.lower())

        if raw_id is not None:
            row_key = f"{site}:{raw_id}"
            self.username_index[lookup] = row_key
        else:
            row_key = self.username_index.get(lookup) or f"{site}:{username.lower()}"
            self.username_index[lookup] = row_key

        if row_key in self.removed_keys:
            return None, None, None

        entry = self.streams.get(row_key)
        was_status = entry.status if entry else None
        if entry is None:
            entry = StreamRowState(
                key=row_key,
                site=_site_display(site),
                account_id=str(raw_id if raw_id is not None else username),
                username=username,
            )
            self.streams[row_key] = entry
        elif raw_id is not None:
            entry.account_id = str(raw_id)

        new_status = str(kw.get("status") or entry.status).lower()
        # Ignore a late "ended" or "stopped" from an exiting recorder when user already clicked Resume ("queued")
        if entry.status == "queued" and not entry.user_stopped and new_status in {"stopped", "ended"}:
            return None, None, None
        if entry.user_stopped and new_status == "ended":
            new_status = "stopped"
        if was_status in {"ended", "failed", "offline", "stopped"} and new_status in {
            "queued",
            "joining",
            "recording",
            "online",
        }:
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
        started_ep = parse_epoch(kw.get("started_at"))
        if started_ep is not None:
            entry.started_epoch = started_ep
        entry.add_part(kw.get("part_path"), kw.get("part_num"))
        entry.updated_at = time.monotonic()

        if new_status in {"ended", "failed", "stopped"}:
            entry.refresh_disk_metrics(time.monotonic())
            entry.speed_bps = 0.0
            if new_status in {"ended", "failed"} and entry.ended_at is None:
                entry.ended_at = time.time()

        return entry, was_status, new_status

    def record_chat(
        self, username: str, total: int | None, line: Text | None
    ) -> StreamRowState | None:
        ukey = username.lower()
        updated_entry = None
        row_key = self.username_index.get(("fansly", ukey))
        if row_key and row_key in self.streams:
            entry = self.streams[row_key]
            entry.chat_count = int(total) if total is not None else (entry.chat_count + 1)
            updated_entry = entry
        if line is not None:
            buf = self.chat_buffers.setdefault(ukey, deque(maxlen=500))
            buf.append(line)
        return updated_entry

    def mark_stopped(
        self,
        entry: StreamRowState,
        *,
        stopped_reason: str = "Stopped by user (click [Resume] or press r)",
    ) -> bool:
        if entry.status not in STOPPABLE_STATUSES:
            return False
        was_rec = entry.status in ACTIVE_STATUSES
        entry.user_stopped = True
        entry.status = "stopping" if was_rec else "stopped"
        entry.reason = "Finalizing recording..." if was_rec else stopped_reason
        return True

    def mark_resumed(
        self,
        entry: StreamRowState,
        *,
        reason: str = "Resuming stream...",
    ) -> bool:
        if entry.status not in RESUMABLE_STATUSES:
            return False
        entry.user_stopped = False
        entry.status = "queued"
        entry.reason = reason
        return True

    def stop_all(self) -> list[StreamRowState]:
        active_entries = [
            e for e in self.streams.values() if e.status in STOPPABLE_STATUSES
        ]
        for entry in active_entries:
            self.mark_stopped(
                entry,
                stopped_reason="Stopped all by user (press a to start all)",
            )
        return active_entries

    def resume_all(self) -> list[StreamRowState]:
        stopped_entries = [
            e for e in self.streams.values() if e.status in RESUMABLE_STATUSES
        ]
        for entry in stopped_entries:
            self.mark_resumed(entry, reason="Resuming on immediate check...")
        return stopped_entries

    def remove_entry(self, entry: StreamRowState) -> None:
        site = entry.key.split(":", 1)[0] if ":" in entry.key else entry.site.lower()
        self.removed_keys.add(entry.key)
        self.removed_user_ids[(site, entry.username.lower())] = entry.account_id
        self.streams.pop(entry.key, None)
        self.prune_username_index()

    def restore_usernames(self, site: str, names: list[str]) -> None:
        for n in names:
            clean = n.lower()
            self.removed_keys.discard(f"{site}:{clean}")
            rk = self.username_index.get((site, clean))
            if rk:
                self.removed_keys.discard(rk)
            removed_id = self.removed_user_ids.pop((site, clean), None)
            if removed_id is not None:
                self.removed_keys.discard(f"{site}:{removed_id}")
            # added back by account id: forget the name it was removed under
            for removed_as in [
                k
                for k, v in self.removed_user_ids.items()
                if k[0] == site and str(v).lower() == clean
            ]:
                del self.removed_user_ids[removed_as]

    def drop_offline_except(self, keep_usernames: set[str]) -> int:
        to_drop = [
            k
            for k, v in self.streams.items()
            if v.status == "offline" and v.username.lower() not in keep_usernames
        ]
        for k in to_drop:
            self.streams.pop(k, None)
        if to_drop:
            self.prune_username_index()
        return len(to_drop)

    def clear_ended(self) -> int:
        to_drop = [
            k for k, v in self.streams.items() if v.status in {"ended", "failed"}
        ]
        for k in to_drop:
            self.streams.pop(k, None)
        if to_drop:
            self.prune_username_index()
        return len(to_drop)
