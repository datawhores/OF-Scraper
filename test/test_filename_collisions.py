import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

import ofscraper.commands.scraper.actions.utils.paths as action_paths
import ofscraper.utils.paths.paths as path_utils


def _media(media_id):
    return SimpleNamespace(id=media_id, post_id=1, model_id=10, username="model")


@pytest.fixture(autouse=True)
def collision_mode(monkeypatch):
    mode = {"value": "media_id"}
    monkeypatch.setattr(
        action_paths.config_data, "get_filename_collision", lambda: mode["value"]
    )
    return mode


def _download(tmp_path, data, name="dl.part"):
    temp = tmp_path / name
    temp.write_bytes(data)
    return temp


def _move(tmp_path, target, media_id, data):
    return action_paths.moveHelper(_download(tmp_path, data), target, _media(media_id))


def test_free_path_is_used(tmp_path):
    target = tmp_path / "caption.jpg"
    assert _move(tmp_path, target, 1, b"media 1") == target
    assert target.read_bytes() == b"media 1"


def test_different_file_keeps_its_name(tmp_path):
    target = tmp_path / "caption.jpg"
    _move(tmp_path, target, 1, b"media 1")
    got = _move(tmp_path, target, 2, b"media 2, larger than media 1")
    assert got == tmp_path / "caption_2.jpg"
    assert target.read_bytes() == b"media 1"
    assert got.read_bytes() == b"media 2, larger than media 1"


def test_identical_file_is_this_download(tmp_path):
    # a re-download (e.g. --force-all) of the same content
    target = tmp_path / "caption.jpg"
    _move(tmp_path, target, 1, b"media 1")
    temp = _download(tmp_path, b"media 1")
    assert action_paths.moveHelper(temp, target, _media(1)) == target
    assert not temp.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["caption.jpg"]


def test_stable_across_runs(tmp_path):
    target = tmp_path / "caption.jpg"
    first = [_move(tmp_path, target, 1, b"media 1"), _move(tmp_path, target, 2, b"media 2")]
    again = [_move(tmp_path, target, 2, b"media 2"), _move(tmp_path, target, 1, b"media 1")]
    assert again == first[::-1]
    assert len(list(tmp_path.iterdir())) == 2


def test_fallback_holding_another_file_is_skipped(tmp_path):
    # media 3's own file sits at caption_2.jpg, media 2's first fallback
    (tmp_path / "caption.jpg").write_bytes(b"media 1")
    (tmp_path / "caption_2.jpg").write_bytes(b"media 3")
    got = _move(tmp_path, tmp_path / "caption.jpg", 2, b"media 2, larger than media 3")
    assert got == tmp_path / "caption_2_2.jpg"
    assert (tmp_path / "caption_2.jpg").read_bytes() == b"media 3"


def test_existing_different_content_is_preserved(tmp_path):
    # Prevention preserves an existing file without interpreting database ownership.
    target = tmp_path / "caption.jpg"
    target.write_bytes(b"media 9, the larger image")
    assert _move(tmp_path, target, 9, b"media 9, the larger image") == target
    got = _move(tmp_path, target, 5, b"media 5")
    assert got == tmp_path / "caption_5.jpg" and got.read_bytes() == b"media 5"


def test_concurrent_moves_to_one_name_keep_every_file(tmp_path):
    target = tmp_path / "caption.jpg"
    temps = [_download(tmp_path, f"media {i}".encode(), f"{i}.part") for i in range(1, 9)]
    results = [None] * 8

    def move(i):
        results[i] = action_paths.moveHelper(temps[i], target, _media(i + 1))

    threads = [threading.Thread(target=move, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(results)) == 8
    assert sorted(p.read_bytes() for p in results) == sorted(f"media {i}".encode() for i in range(1, 9))


def test_overwrite_setting_keeps_old_behaviour(tmp_path, collision_mode):
    collision_mode["value"] = "overwrite"
    target = tmp_path / "caption.jpg"
    _move(tmp_path, target, 1, b"media 1")
    assert _move(tmp_path, target, 2, b"media 2, larger") == target
    assert target.read_bytes() == b"media 2, larger"
    # and the smaller download is dropped, as before
    assert _move(tmp_path, target, 3, b"tiny") == target
    assert target.read_bytes() == b"media 2, larger"


def test_suffix_survives_truncation(tmp_path):
    long = tmp_path / ("x" * 400 + ".mp4")
    out = path_utils.truncate(action_paths.with_media_id(long, 3784819492))
    assert out.name.endswith("_3784819492.mp4")


def test_case_variant_follows_the_filesystem(tmp_path):
    existing = tmp_path / "CaseName.JPG"
    existing.write_bytes(b"media 1")
    same_file = (tmp_path / "casename.jpg").exists()
    got = _move(tmp_path, tmp_path / "casename.jpg", 2, b"media 2")
    assert got == (tmp_path / "casename_2.jpg" if same_file else tmp_path / "casename.jpg")
    assert existing.read_bytes() == b"media 1"


@pytest.fixture
def case_sensitive_dir(tmp_path):
    """A Windows directory with per-directory case sensitivity (as WSL uses)."""
    if sys.platform != "win32":
        pytest.skip("per-directory case sensitivity is a Windows feature")
    d = tmp_path / "cs"
    d.mkdir()
    r = subprocess.run(
        ["fsutil", "file", "setCaseSensitiveInfo", str(d), "enable"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        pytest.skip(f"can't enable case sensitivity here: {r.stdout or r.stderr}")
    return d


@pytest.mark.parametrize("populated", [False, True])
def test_case_sensitive_windows_dir(case_sensitive_dir, tmp_path, populated):
    # reviews on #116: distinct names in a case-sensitive directory, empty or not
    if populated:
        (case_sensitive_dir / "other.txt").write_bytes(b"x")
    upper, lower = case_sensitive_dir / "A.jpg", case_sensitive_dir / "a.jpg"
    assert _move(tmp_path, upper, 1, b"media 1") == upper
    assert _move(tmp_path, lower, 2, b"media 2") == lower
    assert not upper.samefile(lower)
    # next run: same names
    assert _move(tmp_path, lower, 2, b"media 2") == lower
    assert _move(tmp_path, upper, 1, b"media 1") == upper
    assert not (case_sensitive_dir / "a_2.jpg").exists()


def test_metadata_update_keeps_a_recorded_file_under_another_name(tmp_path, monkeypatch):
    # media 2 was saved as caption_2.jpg because caption.jpg held media 1;
    # update mode must not re-point it at caption.jpg
    import ofscraper.commands.metadata.manager as metadata_manager

    (tmp_path / "caption.jpg").write_bytes(b"media 1")
    (tmp_path / "caption_2.jpg").write_bytes(b"media 2")
    prev = {"directory": str(tmp_path), "filename": "caption_2.jpg"}
    manager = metadata_manager.MetaDataManager()
    for mode, expected in [("update", tmp_path / "caption_2.jpg"), ("check", None)]:
        monkeypatch.setattr(metadata_manager.settings, "get_settings", lambda: SimpleNamespace(metadata=mode))
        assert manager._metadata_recorded_file(prev) == expected
    monkeypatch.setattr(metadata_manager.settings, "get_settings", lambda: SimpleNamespace(metadata="update"))
    assert manager._metadata_recorded_file({"directory": str(tmp_path), "filename": "gone.jpg"}) is None


_MOVE_IN_PROCESS = """
import os, sys
from types import SimpleNamespace
temp, target, media_id, gate = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
sys.argv = sys.argv[:1]
import ofscraper.main.open.load  # import order, as in conftest
import ofscraper.commands.scraper.actions.utils.paths as ap
ap.config_data.get_filename_collision = lambda: "media_id"
open(gate + f".ready{media_id}", "w").close()
while not os.path.exists(gate):  # released together
    pass
media = SimpleNamespace(id=media_id, post_id=1, model_id=10, username="model")
print(ap.moveHelper(temp, target, media))
"""


def test_concurrent_processes_reserve_distinct_names(tmp_path):
    # reservation has to hold across processes, not just threads
    import os
    import pathlib
    import time

    target = tmp_path / "caption.jpg"
    temps = [_download(tmp_path, f"media {i}".encode(), f"{i}.part") for i in range(1, 7)]
    repo = pathlib.Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(repo)}
    gate = tmp_path / "go"
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _MOVE_IN_PROCESS, str(t), str(target), str(i + 1), str(gate)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=repo,
        )
        for i, t in enumerate(temps)
    ]
    deadline = time.time() + 90
    while len(list(tmp_path.glob("go.ready*"))) < len(procs):
        assert time.time() < deadline and all(p.poll() is None for p in procs), "a worker failed to start"
        time.sleep(0.05)
    gate.write_bytes(b"")
    results = []
    for p in procs:
        out, err = p.communicate(timeout=90)
        assert p.returncode == 0, err[-2000:]
        results.append(out.strip().splitlines()[-1])
    assert len(set(results)) == 6
    contents = sorted(Path(r).read_bytes() for r in results)
    assert contents == sorted(f"media {i}".encode() for i in range(1, 7))


def test_another_downloads_reservation_is_left_alone(tmp_path):
    target = tmp_path / "caption.jpg"
    target.write_bytes(b"")  # reserved by another download, not filled yet
    got = _move(tmp_path, target, 2, b"media 2")
    assert got == tmp_path / "caption_2.jpg"
    assert target.read_bytes() == b""


def test_temp_on_another_drive_is_copied(tmp_path, monkeypatch):
    import errno
    import os

    replace = os.replace
    temp = _download(tmp_path, b"media 1")

    def cross_device(src, dst):
        if src == temp:
            raise OSError(errno.EXDEV, "cross-device link")
        return replace(src, dst)

    monkeypatch.setattr(os, "replace", cross_device)
    got = action_paths.moveHelper(temp, tmp_path / "caption.jpg", _media(1))
    assert got.read_bytes() == b"media 1" and not temp.exists()


def test_cross_drive_move_sweeps_abandoned_staging_files(tmp_path, monkeypatch):
    import errno
    import os
    import time

    stale = tmp_path / ".ofs-move-killed"
    fresh = tmp_path / ".ofs-move-in-progress"
    stale.write_bytes(b"partial")
    fresh.write_bytes(b"partial")
    old = time.time() - action_paths.STALE_STAGING_SECONDS - 60
    os.utime(stale, (old, old))
    replace = os.replace
    temp = _download(tmp_path, b"media 1")

    def cross_device(src, dst):
        if src == temp:
            raise OSError(errno.EXDEV, "cross-device link")
        return replace(src, dst)

    monkeypatch.setattr(os, "replace", cross_device)
    action_paths.moveHelper(temp, tmp_path / "caption.jpg", _media(1))
    assert not stale.exists() and fresh.exists()


def test_sweep_spares_a_live_copy_of_an_old_download(tmp_path, monkeypatch):
    import errno
    import os
    import time

    # A .part completed by a killed run is moved without being rewritten, so
    # its mtime can be days old. Another download moving into the same folder
    # sweeps it while this copy is about to be published.
    temp = _download(tmp_path, b"media 1")
    old = time.time() - 2 * action_paths.STALE_STAGING_SECONDS
    os.utime(temp, (old, old))
    replace, publish = os.replace, action_paths._replace

    def cross_device(src, dst):
        if src == temp:
            raise OSError(errno.EXDEV, "cross-device link")
        return replace(src, dst)

    def publish_after_concurrent_sweep(src, dst):
        if ".ofs-move-" in str(src):
            action_paths._sweep_staging(dst.parent)
        return publish(src, dst)

    monkeypatch.setattr(os, "replace", cross_device)
    monkeypatch.setattr(action_paths, "_replace", publish_after_concurrent_sweep)
    got = action_paths.moveHelper(temp, tmp_path / "caption.jpg", _media(1))
    assert got.read_bytes() == b"media 1"
    assert abs(got.stat().st_mtime - old) < 1 and not temp.exists()


def test_failed_move_removes_its_reservation(tmp_path, monkeypatch):
    import os

    def denied(src, dst):
        raise PermissionError("denied")

    monkeypatch.setattr(os, "replace", denied)
    with pytest.raises(PermissionError):
        _move(tmp_path, tmp_path / "caption.jpg", 1, b"media 1")
    assert not (tmp_path / "caption.jpg").exists()


def test_failed_move_leaves_other_files_alone(tmp_path, monkeypatch):
    # the planned name holds another file; only the fallback was reserved
    import os

    (tmp_path / "caption.jpg").write_bytes(b"media 1")

    def denied(src, dst):
        raise PermissionError("denied")

    monkeypatch.setattr(os, "replace", denied)
    with pytest.raises(PermissionError):
        _move(tmp_path, tmp_path / "caption.jpg", 2, b"media 2")
    assert (tmp_path / "caption.jpg").read_bytes() == b"media 1"
    assert not (tmp_path / "caption_2.jpg").exists()


@pytest.mark.parametrize("fail_copy", [False, True])
def test_cross_drive_partial_copy_is_not_deduplicated(tmp_path, monkeypatch, fail_copy):
    import errno
    import os
    from pathlib import Path

    target = tmp_path / "caption.jpg"
    temp = _download(tmp_path, b"prefix and remainder", "first.part")
    second = _download(tmp_path, b"prefix", "second.part")
    replace = os.replace
    results = []

    def cross_device(src, dst):
        if src == temp:
            raise OSError(errno.EXDEV, "cross-device link")
        return replace(src, dst)

    def interrupted_copy(src, dst):
        Path(dst).write_bytes(b"prefix")
        # Deterministically interleave a second completed download mid-copy.
        results.append(action_paths.moveHelper(second, target, _media(2)))
        if fail_copy:
            raise OSError("copy interrupted")
        Path(dst).write_bytes(Path(src).read_bytes())

    monkeypatch.setattr(os, "replace", cross_device)
    monkeypatch.setattr(action_paths.shutil, "copyfile", interrupted_copy)
    if fail_copy:
        with pytest.raises(OSError, match="copy interrupted"):
            action_paths.moveHelper(temp, target, _media(1))
        assert temp.exists() and not target.exists()
    else:
        assert action_paths.moveHelper(temp, target, _media(1)) == target
        assert target.read_bytes() == b"prefix and remainder"
    assert results == [tmp_path / "caption_2.jpg"]
    assert results[0].read_bytes() == b"prefix"
    assert not list(tmp_path.glob(".ofs-move-*"))


def test_empty_download_does_not_consume_another_reservation(tmp_path):
    target = tmp_path / "caption.jpg"
    assert action_paths._reserve(target)
    assert _move(tmp_path, target, 2, b"") == tmp_path / "caption_2.jpg"
    assert target.exists()


@pytest.mark.parametrize("permanent", [False, True])
def test_windows_sharing_error_keeps_reservation_during_retry(tmp_path, monkeypatch, permanent):
    import os
    replace = os.replace
    target = tmp_path / "caption.jpg"
    temp = _download(tmp_path, b"media")
    attempts = []

    def busy(src, dst):
        assert target.is_file() and target.stat().st_size == 0
        attempts.append(dst)
        if permanent or len(attempts) == 1:
            error = PermissionError("sharing conflict")
            error.winerror = 5
            raise error
        return replace(src, dst)

    monkeypatch.setattr(os, "replace", busy)
    monkeypatch.setattr(action_paths.time, "sleep", lambda delay: None)
    if permanent:
        with pytest.raises(PermissionError):
            action_paths.moveHelper(temp, target, _media(1))
        assert len(attempts) == 6
        assert temp.exists() and not target.exists()
    else:
        assert action_paths.moveHelper(temp, target, _media(1)) == target
        assert len(attempts) == 2 and target.read_bytes() == b"media"


def test_disappearing_reservation_is_not_an_error(tmp_path, monkeypatch):
    target = tmp_path / "caption.jpg"
    target.write_bytes(b"same size")
    temp = _download(tmp_path, b"same size")
    original = action_paths._file_hash

    def disappear(path):
        if path == target:
            target.unlink()
        return original(path)

    monkeypatch.setattr(action_paths, "_file_hash", disappear)
    assert not action_paths._same_content(temp, target)
    assert temp.exists()


@pytest.mark.parametrize("downloader", ["normal", "drm"])
def test_downloaders_record_and_use_final_path(tmp_path, monkeypatch, downloader):
    import asyncio
    from unittest.mock import AsyncMock, Mock
    import ofscraper.commands.scraper.actions.download.managers.main_download as normal
    import ofscraper.commands.scraper.actions.download.managers.alt_download as drm

    module = normal if downloader == "normal" else drm
    target = tmp_path / "caption.jpg"
    target.write_bytes(b"existing owner")
    final = tmp_path / "caption_2.jpg"
    payload = b"new download"
    temp = tmp_path / "download.part"
    placeholder = SimpleNamespace(trunicated_filepath=target, size=999)
    ele = _media(2)
    ele.mediatype, ele.postdate, ele.duration = "Images", "2020-01-01", 1
    ele.add_filepath = Mock()

    async def filename():
        return target.name

    ele.final_filename = filename() if downloader == "normal" else None
    manager = SimpleNamespace(_size_checker=AsyncMock(), _after_download_script=AsyncMock())
    database = AsyncMock()
    hashing = AsyncMock(return_value="new-hash")
    dating = Mock()
    monkeypatch.setattr(module.common_globals, "thread", None, raising=False)
    monkeypatch.setattr(module.common_globals, "log", Mock())
    monkeypatch.setattr(module, "mark_media_as_downloaded", database)
    monkeypatch.setattr(module.common, "get_hash", hashing)
    monkeypatch.setattr(module.common_paths, "set_time", dating)
    monkeypatch.setattr(module.common_paths, "addGlobalDir", Mock())
    if downloader == "normal":
        temp.write_bytes(payload)
        monkeypatch.setattr(normal, "set_profile_cache", AsyncMock())
        asyncio.run(normal.MainDownloadManager._handle_result_main(
            manager, (len(payload), temp, placeholder), ele, "model", 10
        ))
    else:
        monkeypatch.setattr(drm.placeholder, "tempFilePlaceholder", lambda *a: SimpleNamespace(
            init=AsyncMock(return_value=SimpleNamespace(tempfilepath=temp))
        ))

        async def merge(*args, **kwargs):
            temp.write_bytes(payload)
            return SimpleNamespace(stderr=b"", stdout=b"")

        monkeypatch.setattr(drm, "async_run", merge)
        monkeypatch.setattr(drm, "get_ffmpeg", lambda: "ffmpeg")
        monkeypatch.setattr(drm, "verify_media_integrity", lambda *a: True)
        asyncio.run(drm.AltDownloadManager._handle_result_alt(
            manager, placeholder, ele, None, None, "model", 10
        ))
    assert target.read_bytes() == b"existing owner"
    assert final.read_bytes() == payload
    assert database.await_args.kwargs["filepath"] == final
    assert database.await_args.kwargs["size"] == len(payload)
    assert database.await_args.kwargs["hashdata"] == "new-hash"
    hashing.assert_awaited_once_with(final)
    assert dating.call_args.args[0] == final
    ele.add_filepath.assert_called_once_with(final)
    manager._after_download_script.assert_awaited_once_with(final)
