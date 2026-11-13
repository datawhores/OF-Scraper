"""temp_cleanup() removes temp_ files by name, not by full path."""

from types import SimpleNamespace

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.paths.paths as paths


def _run_cleanup(monkeypatch, root):
    real_getattr = paths.of_env.getattr

    def fake_getattr(key, *args, **kwargs):
        if key == "BATCH_TEMPFILE_CLEANUP":
            return True
        return real_getattr(key, *args, **kwargs)

    monkeypatch.setattr(paths.of_env, "getattr", fake_getattr)
    monkeypatch.setattr(
        paths.settings, "get_settings", lambda: SimpleNamespace(auto_resume=False)
    )
    monkeypatch.setattr(paths.data, "get_TempDir", lambda *a, **k: str(root))
    paths.temp_cleanup()


def test_removes_temp_prefixed_files(monkeypatch, tmp_path):
    sub = tmp_path / "creator" / "Videos"
    sub.mkdir(parents=True)
    temp_top = tmp_path / "temp_123.mp4"
    temp_nested = sub / "temp_456.mp4"
    part = sub / "video.mp4.part"
    for f in (temp_top, temp_nested, part):
        f.write_bytes(b"x")

    _run_cleanup(monkeypatch, tmp_path)

    assert not temp_top.exists()
    assert not temp_nested.exists()
    assert not part.exists()


def test_keeps_other_files_and_folders(monkeypatch, tmp_path):
    # A folder named temp_ is left alone, and so is a file inside it or
    # with temp_ in the middle of its name.
    temp_dir = tmp_path / "temp_folder"
    temp_dir.mkdir()
    inside = temp_dir / "keep.mp4"
    middle = tmp_path / "my_temp_clip.mp4"
    done = tmp_path / "finished.mp4"
    for f in (inside, middle, done):
        f.write_bytes(b"x")

    _run_cleanup(monkeypatch, tmp_path)

    assert temp_dir.is_dir()
    assert inside.exists()
    assert middle.exists()
    assert done.exists()
