"""--dry-run: scan as usual, download nothing, change nothing.

The scan writes to the creator databases and the cache in many places, so a
dry run doesn't try to stop each write. It points the scan at throwaway
copies instead: each creator's database is copied the first time it is
used (through sqlite's backup while another run has it open), and the
profile's cache folder is copied when the cache is first opened. The copies
are removed at the end of the run. The real files are never written to.
"""

import atexit
import contextlib
import hashlib
import json
import logging
import pathlib
import shutil
import sqlite3
import tempfile
import threading

import ofscraper.utils.settings as settings

log = logging.getLogger("shared")

_lock = threading.Lock()
_root = None
_copies = {}
# per creator: {(area, type): {"count": n, "protected": n}} and sample paths
_counts = {}
_samples = {}
# per creator: the media ids already counted
_seen = {}
SAMPLES_PER_CREATOR = 3


def active():
    try:
        s = settings.get_settings()
        return bool(getattr(s, "dry_run", False) or getattr(s, "dry_run_json", None))
    except Exception:
        return False


def _workdir():
    global _root
    if _root is None:
        _root = pathlib.Path(tempfile.mkdtemp(prefix="ofscraper-dry-run-"))
        atexit.register(cleanup)
    return _root


def _state(paths):
    """Size and modified time of each path, or None where it is missing."""
    out = []
    for path in paths:
        try:
            st = path.stat()
            out.append((st.st_size, st.st_mtime_ns))
        except FileNotFoundError:
            out.append(None)
    return out


def _backup(src, dest):
    """A consistent copy through sqlite, rows still in the write-ahead log
    included. Read-only: nothing is written to src."""
    uri = src.absolute().as_uri() + "?mode=ro"
    with contextlib.closing(sqlite3.connect(uri, uri=True)) as source:
        with contextlib.closing(sqlite3.connect(dest)) as target:
            source.backup(target)


def _copy_file(src, dest):
    """Copy a database so the copy holds every committed row.

    While a run has the database open in WAL mode (its -wal and -shm exist),
    the file and the -wal are copied together by sqlite's backup, since a
    checkpoint between two file copies would lose rows. Without a -shm no
    connection is open, and opening one, even read-only, would create a -wal
    and -shm beside the real file; then the file and any leftover -wal are
    copied as they are, again if they changed meanwhile."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return
    wal = src.with_name(src.name + "-wal")
    shm = src.with_name(src.name + "-shm")
    dest_wal = dest.with_name(dest.name + "-wal")
    for _ in range(3):
        if shm.exists():
            break
        before = _state((src, wal, shm))
        shutil.copy2(src, dest)
        if wal.exists():
            shutil.copy2(wal, dest_wal)
        if _state((src, wal, shm)) == before:
            return
        for path in (dest, dest_wal):
            path.unlink(missing_ok=True)
    _backup(src, dest)


def _copy_dir(src, dest):
    if src.exists():
        shutil.copytree(src, dest)
    else:
        dest.mkdir(parents=True, exist_ok=True)


def redirect(real_path, folder=False):
    """The throwaway copy to use for real_path, made the first time it is
    asked for. folder=True copies a whole folder (the cache)."""
    real = pathlib.Path(real_path)
    key = str(real.resolve() if real.exists() else real.absolute())
    with _lock:
        if key in _copies:
            return _copies[key]
        name = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        dest = _workdir() / name / real.name
        if folder:
            _copy_dir(real, dest)
        else:
            _copy_file(real, dest)
        _copies[key] = dest
        log.debug(f"dry run: using a copy of {real}")
        return dest


def cleanup():
    """Remove the copies. Safe to call more than once."""
    global _root
    # the cache may hold the copy open: close it, and forget it so a later
    # use opens the cache path afresh rather than the removed copy
    try:
        import ofscraper.utils.cache.cache as cache

        with cache.lock:
            if cache.cache is not None:
                cache.cache.close()
                cache.cache = None
    except Exception:
        pass
    with _lock:
        root, _root = _root, None
        _copies.clear()
    if root is not None:
        shutil.rmtree(root, ignore_errors=True)


def refuse_reason():
    """Why this run can't be a dry run, or None."""
    import ofscraper.db.postgres as postgres

    if postgres.enabled():
        return (
            "--dry-run doesn't work with PostgreSQL yet: it can't take a throwaway "
            "copy of the database. Run it without the PostgreSQL setting."
        )
    return None


def _extension(ele):
    """The extension a download would most likely get: from the link for an
    ordinary file (the real one comes from the reply), mp4 for protected
    video."""
    if getattr(ele, "protected", False):
        return "mp4"
    try:
        suffix = pathlib.PurePosixPath((ele.url or ele.link or "").split("?")[0]).suffix
    except Exception:
        suffix = ""
    if suffix and len(suffix) <= 6:
        return suffix[1:].lower()
    from ofscraper.commands.scraper.actions.utils.general import get_unknown_content_type

    return get_unknown_content_type(ele) or "bin"


async def _expected_path(ele):
    import ofscraper.classes.placeholder as placeholder

    holder = await placeholder.Placeholders(ele, _extension(ele)).init(create=False)
    return str(holder.filepath)


async def record(username, media):
    """Count what a download would have attempted for a creator, by area and
    type, and work out a few expected paths."""
    media = list(media or [])
    with _lock:
        # --scrape-paid passes purchased media again after the creator's
        # own areas: count each media id once
        seen = _seen.setdefault(username, set())
        fresh = []
        for ele in media:
            media_id = getattr(ele, "id", None)
            if media_id is not None:
                if media_id in seen:
                    continue
                seen.add(media_id)
            fresh.append(ele)
        media = fresh
        areas = _counts.setdefault(username, {})
        for ele in media:
            key = (str(getattr(ele, "responsetype", "") or "unknown").lower(),
                   str(getattr(ele, "mediatype", "") or "unknown").lower())
            entry = areas.setdefault(key, {"count": 0, "protected": 0})
            entry["count"] += 1
            if getattr(ele, "protected", False):
                entry["protected"] += 1
        samples = _samples.setdefault(username, [])
        wanted = SAMPLES_PER_CREATOR - len(samples)
    # one sample per area first, then any
    picked, seen = [], set()
    for ele in media:
        area = getattr(ele, "responsetype", None)
        if len(picked) < wanted and area not in seen:
            picked.append(ele)
            seen.add(area)
    for ele in media:
        if len(picked) >= wanted:
            break
        if ele not in picked:
            picked.append(ele)
    for ele in picked:
        try:
            path = await _expected_path(ele)
        except Exception as e:
            log.debug(f"dry run: no expected path for media {getattr(ele, 'id', '?')}: {e}")
            continue
        with _lock:
            _samples[username].append(path)


def reset():
    with _lock:
        _counts.clear()
        _samples.clear()
        _seen.clear()


def finish():
    """Report a scan that finished, then forget it and remove the copies, so
    a next pass (infinite_loop_action_mode) starts again from the real files."""
    try:
        log.warning(report())
        json_path = getattr(settings.get_settings(), "dry_run_json", None)
        if json_path:
            write_json(json_path)
            log.warning(f"Dry run report written to {json_path}")
    finally:
        reset()
        cleanup()


def data():
    """The report as data (--dry-run-json)."""
    s = settings.get_settings()
    with _lock:
        creators = []
        for username in sorted(_counts, key=str.lower):
            areas = [
                {"area": area, "type": kind, **entry}
                for (area, kind), entry in sorted(_counts[username].items())
            ]
            creators.append({
                "username": username,
                "to_download": sum(a["count"] for a in areas),
                "areas": areas,
                "sample_paths": list(_samples.get(username, [])),
            })
    return {
        "dry_run": True,
        "to_download": sum(c["to_download"] for c in creators),
        "creators": creators,
        "limits_not_applied": [
            name for name in ("size_max", "size_min", "skip_download_script")
            if getattr(s, name, None)
        ],
    }


def _plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _count_of(n, kind):
    """'1 video', '2 videos': the types are plural words (Videos, Images)."""
    if n == 1 and kind.endswith("s"):
        kind = kind[:-1]
    return f"{n} {kind}"


def report():
    """What the dry run would have done, as text."""
    d = data()
    lines = ["Dry run: nothing was downloaded and nothing was changed."]
    for creator in d["creators"]:
        lines.append("")
        lines.append(creator["username"])
        by_area = {}
        for a in creator["areas"]:
            by_area.setdefault(a["area"], []).append(a)
        for area, kinds in by_area.items():
            total = sum(k["count"] for k in kinds)
            parts = ", ".join(_count_of(k["count"], k["type"]) for k in kinds)
            protected = sum(k["protected"] for k in kinds)
            extra = f", {protected} protected" if protected else ""
            lines.append(f"  {area:<12}{total:>5} to download ({parts}{extra})")
        if creator["sample_paths"]:
            lines.append("  Sample paths (expected):")
            lines.extend(f"    {p}" for p in creator["sample_paths"])
    lines.append("")
    lines.append(
        f"A download would attempt up to {_plural(d['to_download'], 'file')} "
        f"from {_plural(len(d['creators']), 'creator')}."
    )
    if d["limits_not_applied"]:
        lines.append(
            'Counts are "up to": size limits and skip_download_script are decided '
            "during a download, so they aren't applied here."
        )
    lines.append(
        "Paths are expected paths: the extension comes from the link (mp4 for "
        "protected video), and naming_script isn't run."
    )
    return "\n".join(lines)


def write_json(path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data(), f, indent=2, ensure_ascii=False)
