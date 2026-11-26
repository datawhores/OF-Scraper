"""--dry-run: the scan runs on throwaway copies and nothing is downloaded or
changed (utils/dry_run.py)."""

import asyncio
import contextlib
import os
import sqlite3
from types import SimpleNamespace

import pytest
from click.exceptions import UsageError

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.scraper.actions.download.download as download
import ofscraper.db.operations_.media as media_ops
import ofscraper.scripts.after_download_action_script as after_download
import ofscraper.scripts.after_like_action_script as after_like
import ofscraper.scripts.final_script as final_script
import ofscraper.sites.fansly.pipeline as pipeline
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.dry_run as dry_run
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.paths.paths as paths
import ofscraper.utils.settings as settings
from ofscraper.utils.args.parse.group_bundles.main import check_dry_run


def snapshot(root):
    """Every file under root with its bytes and modified time."""
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            st = path.stat()
            out[str(path.relative_to(root))] = (path.read_bytes(), st.st_mtime_ns)
        else:
            out[str(path.relative_to(root))] = None
    return out


def make_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.execute(media_ops.mediaCreate)
        conn.execute(
            "INSERT INTO medias (media_id, post_id, api_type, media_type,"
            " created_at, posted_at, model_id) VALUES (1, 100, 'timeline',"
            " 'Images', '2024-01-01', '2024-01-02', 5)"
        )
        conn.commit()


def media_ids(path):
    with contextlib.closing(sqlite3.connect(path)) as conn:
        return sorted(r[0] for r in conn.execute("SELECT media_id FROM medias"))


@pytest.fixture
def library(monkeypatch, tmp_path):
    """A profile under tmp_path with one creator's database and a cache,
    using the real path helpers."""
    monkeypatch.setattr(placeholder.log, "trace", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(placeholder.me, "parse_user", lambda: ("1", "me"))
    monkeypatch.setattr(placeholder.me, "get_id", lambda: 1)
    monkeypatch.setattr(placeholder.profile_data, "get_active_profile", lambda: "main_profile")
    monkeypatch.setattr(placeholder.common_paths, "get_config_home", lambda: tmp_path / "cfg")
    monkeypatch.setattr(
        placeholder.common_paths, "get_save_location", lambda *a, **k: str(tmp_path / "data")
    )
    monkeypatch.setattr(
        placeholder.data, "get_metadata", lambda *a, **k: "{configpath}/{profile}/.data/{model_username}"
    )
    profile = tmp_path / "cfg" / "main_profile"
    monkeypatch.setattr(common_paths, "get_profile_path", lambda *a, **k: profile)
    s = settings.get_settings()
    monkeypatch.setitem(s, "cached_disabled", False)
    monkeypatch.setitem(s, "dry_run", False)
    monkeypatch.setattr(cache, "cache", None)
    make_db(profile / ".data" / "a creator" / "user_data.db")
    cache.set("scan_mark", "real", auto_close=True)
    cache.cache.close()
    cache.cache = None
    dry_run.reset()
    yield SimpleNamespace(root=tmp_path, profile=profile, settings=s)
    # runs even when the test failed, so counts never leak into the next test
    dry_run.reset()
    dry_run.cleanup()
    if cache.cache is not None:
        cache.cache.close()
        cache.cache = None


def test_dry_run_changes_nothing(library, monkeypatch):
    # Given a library with a creator's database and a cache
    before = snapshot(library.root)
    monkeypatch.setitem(library.settings, "dry_run", True)

    # When a dry run's scan writes to the database and the cache, as a scan does
    real = library.profile / ".data" / "a creator" / "user_data.db"
    copy = placeholder.databasePlaceholder().databasePathHelper(5, "a creator")
    with contextlib.closing(sqlite3.connect(copy)) as conn:
        conn.execute(
            "INSERT INTO medias (media_id, post_id, api_type, media_type,"
            " created_at, posted_at, model_id) VALUES (2, 101, 'timeline',"
            " 'Images', '2024-01-01', '2024-01-02', 5)"
        )
        conn.commit()
    asyncio.run(media_ops.create_media_table(model_id=6, username="new creator"))
    assert cache.get("scan_mark") == "real"  # the copy starts from the real cache
    cache.set("scan_mark", "dry run")

    # Then the scan saw a copy of the real rows and wrote to it
    assert copy != real and media_ids(copy) == [1, 2]
    # and after cleanup nothing in the library changed, not even a new folder
    dry_run.cleanup()
    assert snapshot(library.root) == before
    assert not copy.exists()

    # and a normal run afterwards uses the real files, as they were
    monkeypatch.setitem(library.settings, "dry_run", False)
    assert placeholder.databasePlaceholder().databasePathHelper(5, "a creator") == real
    assert media_ids(real) == [1]
    assert cache.get("scan_mark") == "real"


def test_copies_are_removed_after_an_error(library, monkeypatch):
    monkeypatch.setitem(library.settings, "dry_run", True)
    copy = placeholder.databasePlaceholder().databasePathHelper(5, "a creator")
    root = dry_run._root
    assert copy.exists() and root.exists()
    try:
        raise RuntimeError("scan failed")
    except RuntimeError:
        dry_run.cleanup()
    assert not root.exists()


def test_copy_includes_rows_still_in_the_write_ahead_log(library, monkeypatch):
    real = library.profile / ".data" / "a creator" / "user_data.db"
    with contextlib.closing(sqlite3.connect(real)) as keep_open:
        keep_open.execute("PRAGMA journal_mode=WAL")
        keep_open.execute("PRAGMA wal_autocheckpoint=0")
        keep_open.execute(
            "INSERT INTO medias (media_id, post_id, api_type, media_type,"
            " created_at, posted_at, model_id) VALUES (3, 102, 'timeline',"
            " 'Images', '2024-01-01', '2024-01-02', 5)"
        )
        keep_open.commit()
        assert (real.parent / "user_data.db-wal").stat().st_size > 0
        monkeypatch.setitem(library.settings, "dry_run", True)
        copy = placeholder.databasePlaceholder().databasePathHelper(5, "a creator")
        assert media_ids(copy) == [1, 3]



def test_a_checkpoint_during_the_copy_loses_no_row(library, monkeypatch):
    # Given a creator's database with a committed row still in the
    # write-ahead log, held open by another run
    real = library.profile / ".data" / "a creator" / "user_data.db"
    with contextlib.closing(sqlite3.connect(real)) as other_run:
        other_run.execute("PRAGMA journal_mode=WAL")
        other_run.execute("PRAGMA wal_autocheckpoint=0")
        other_run.execute(
            "INSERT INTO medias (media_id, post_id, api_type, media_type,"
            " created_at, posted_at, model_id) VALUES (3, 102, 'timeline',"
            " 'Images', '2024-01-01', '2024-01-02', 5)"
        )
        other_run.commit()
        # When that run checkpoints while the dry run is copying a file
        real_copy2 = dry_run.shutil.copy2

        def copy_then_checkpoint(*args, **kwargs):
            out = real_copy2(*args, **kwargs)
            other_run.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            return out

        monkeypatch.setattr(dry_run.shutil, "copy2", copy_then_checkpoint)
        monkeypatch.setitem(library.settings, "dry_run", True)
        copy = placeholder.databasePlaceholder().databasePathHelper(5, "a creator")
        # Then the copy still has the committed row
        assert media_ids(copy) == [1, 3]


def _sidecars(real):
    return sorted(p.name for p in real.parent.iterdir() if p.name != real.name)


def test_a_closed_wal_database_gets_no_new_files(library, monkeypatch):
    # Given a database in WAL mode that no run has open (no -wal, no -shm)
    real = library.profile / ".data" / "a creator" / "user_data.db"
    with contextlib.closing(sqlite3.connect(real)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
    assert _sidecars(real) == []
    before = snapshot(library.root)
    # When a dry run copies it
    monkeypatch.setitem(library.settings, "dry_run", True)
    copy = placeholder.databasePlaceholder().databasePathHelper(5, "a creator")
    # Then the copy has its rows and no -wal or -shm appeared beside the real file
    assert media_ids(copy) == [1]
    assert _sidecars(real) == []
    dry_run.cleanup()
    assert snapshot(library.root) == before


def test_a_leftover_write_ahead_log_is_copied_without_touching_it(library, monkeypatch):
    # Given a run that stopped with committed rows still in the -wal, and no -shm
    real = library.profile / ".data" / "a creator" / "user_data.db"
    work = library.root / "work"
    work.mkdir()
    make_db(work / "user_data.db")
    with contextlib.closing(sqlite3.connect(work / "user_data.db")) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute(
            "INSERT INTO medias (media_id, post_id, api_type, media_type,"
            " created_at, posted_at, model_id) VALUES (3, 102, 'timeline',"
            " 'Images', '2024-01-01', '2024-01-02', 5)"
        )
        conn.commit()
        for name in ("user_data.db", "user_data.db-wal"):
            (real.parent / name).write_bytes((work / name).read_bytes())
    assert _sidecars(real) == ["user_data.db-wal"]
    before = snapshot(library.profile)
    # When a dry run copies it
    monkeypatch.setitem(library.settings, "dry_run", True)
    copy = placeholder.databasePlaceholder().databasePathHelper(5, "a creator")
    # Then the copy has the rows from the log, and the real files are as they were
    assert media_ids(copy) == [1, 3]
    assert snapshot(library.profile) == before



@pytest.mark.parametrize("dry", [True, False])
def test_startup_migrates_an_old_config_only_outside_a_dry_run(monkeypatch, tmp_path, dry):
    import json

    import ofscraper.main.open.load as load
    import ofscraper.utils.config.config as config_

    # Given a config.json in an older form, missing most settings
    path = tmp_path / "config.json"
    old = json.dumps({"config": {"main_profile": "main_profile"}}, indent=4)
    path.write_text(old, encoding="utf-8")
    # a whole, even second: every file system stores it exactly (NTFS keeps
    # 100 ns steps, FAT two seconds)
    os.utime(path, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
    monkeypatch.setattr(common_paths, "get_config_path", lambda: path)
    monkeypatch.setattr(config_, "config", None)  # read_config's cache
    monkeypatch.setitem(settings.get_settings(), "dry_run", dry)

    # When the app reads its config at startup
    load.readConfig()

    # Then a dry run leaves the file as it was, and a normal run updates it
    unchanged = (
        path.read_text(encoding="utf-8") == old
        and path.stat().st_mtime_ns == 1_600_000_000_000_000_000
    )
    assert unchanged is dry
    if not dry:
        assert "file_options" in json.loads(path.read_text(encoding="utf-8"))


# --- the switch-off list ----------------------------------------------------


@pytest.fixture
def event_loop_for_app():
    """The app's run wrapper uses the current loop; give it one and close it."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


def test_download_is_counted_not_run(monkeypatch, library, event_loop_for_app):
    called = []

    async def process_dicts(*a, **k):
        called.append(a)
        return (1, 0, 0, 0, 0)

    monkeypatch.setattr(download, "process_dicts", process_dicts)
    monkeypatch.setattr(download, "remove_downloads_with_hashes", lambda *a: called.append("dupes"))
    monkeypatch.setitem(library.settings, "text_only", False)
    monkeypatch.setitem(library.settings, "size_max", None)
    monkeypatch.setitem(library.settings, "size_min", None)
    monkeypatch.setitem(library.settings, "skip_download_script", None)
    dry_run.reset()

    monkeypatch.setitem(library.settings, "dry_run", True)
    assert download.download_process("a creator", 5, [object(), object()], []) == (0, 0, 0, 0, 0)
    assert called == []
    assert dry_run.data()["to_download"] == 2

    monkeypatch.setitem(library.settings, "dry_run", False)
    download.download_process("a creator", 5, [object()], [])
    assert called and called[-1] == "dupes"


def test_report_says_size_limits_are_not_applied(monkeypatch, library):
    monkeypatch.setitem(library.settings, "size_max", 1000)
    dry_run.reset()
    assert "aren't applied" in dry_run.report()
    assert dry_run.data()["limits_not_applied"] == ["size_max"]


# --- the report -------------------------------------------------------------


def media(area, kind, media_id, protected=False, url=None):
    return SimpleNamespace(
        id=media_id, responsetype=area, mediatype=kind, protected=protected,
        url=url, link=url,
    )


@pytest.fixture
def report_env(monkeypatch, library):
    """Expected paths from a stand-in Placeholders that records how it was built."""
    built = []

    class FakePlaceholders:
        def __init__(self, ele, ext):
            self.ele, self.ext = ele, ext

        async def init(self, create=True):
            built.append((self.ele.id, self.ext, create))
            self.filepath = f"lib/{self.ele.responsetype}/{self.ele.id}.{self.ext}"
            return self

    import ofscraper.classes.placeholder as placeholder_module

    monkeypatch.setattr(placeholder_module, "Placeholders", FakePlaceholders)
    for name in ("size_max", "size_min", "skip_download_script"):
        monkeypatch.setitem(library.settings, name, None)
    dry_run.reset()
    yield built
    dry_run.reset()


def test_report_by_creator_area_and_type(report_env):
    asyncio.run(dry_run.record("b creator", [
        media("Timeline", "Images", 1, url="https://cdn.example/a/1.jpeg?sig=x"),
        media("Timeline", "Images", 2, url="https://cdn.example/a/2.jpg"),
        media("Timeline", "Videos", 3, url="https://cdn.example/a/3.mp4"),
        media("Messages", "Videos", 4, protected=True),
    ]))
    asyncio.run(dry_run.record("a creator", [media("Timeline", "Images", 5, url="https://x/5.png")]))

    d = dry_run.data()
    assert d["to_download"] == 5
    assert [c["username"] for c in d["creators"]] == ["a creator", "b creator"]
    b = d["creators"][1]
    assert b["areas"] == [
        {"area": "messages", "type": "videos", "count": 1, "protected": 1},
        {"area": "timeline", "type": "images", "count": 2, "protected": 0},
        {"area": "timeline", "type": "videos", "count": 1, "protected": 0},
    ]
    # one sample per area first; the link's extension, mp4 for protected video;
    # and the paths are worked out without making folders
    assert b["sample_paths"] == ["lib/Timeline/1.jpeg", "lib/Messages/4.mp4", "lib/Timeline/2.jpg"]
    assert all(create is False for _, _, create in report_env)

    text = dry_run.report()
    assert text.startswith("Dry run: nothing was downloaded and nothing was changed.")
    assert "  timeline        3 to download (2 images, 1 video)" in text
    assert "  messages        1 to download (1 video, 1 protected)" in text
    assert "    lib/Messages/4.mp4" in text
    assert "A download would attempt up to 5 files from 2 creators." in text
    assert "aren't applied" not in text


def test_samples_stop_at_three_per_creator(report_env):
    asyncio.run(dry_run.record("a creator", [media("Timeline", "Images", i, url=f"https://x/{i}.jpg") for i in range(10)]))
    asyncio.run(dry_run.record("a creator", [media("Messages", "Images", 99, url="https://x/99.jpg")]))
    assert len(dry_run.data()["creators"][0]["sample_paths"]) == 3
    assert dry_run.data()["to_download"] == 11


def test_media_seen_twice_is_counted_once(report_env):
    """--scrape-paid passes purchased media again after the creator's own
    areas: one file, one count."""
    asyncio.run(dry_run.record("a creator", [
        media("Messages", "Videos", 7, url="https://x/7.mp4"),
        media("Timeline", "Images", 8, url="https://x/8.jpg"),
    ]))
    asyncio.run(dry_run.record("a creator", [media("Messages", "Videos", 7, url="https://x/7.mp4")]))
    d = dry_run.data()
    assert d["to_download"] == 2
    assert len(d["creators"][0]["sample_paths"]) == 2


@pytest.mark.parametrize("dry", [True, False])
def test_expired_logs_are_deleted_only_outside_a_dry_run(monkeypatch, library, tmp_path, dry):
    import ofscraper.utils.paths.manage as manage

    logs = tmp_path / "logs"
    old = logs / "main_profile_2020-01-01" / "old.log"
    old.parent.mkdir(parents=True)
    old.write_text("old", encoding="utf-8")
    os.utime(old, (1_000_000_000, 1_000_000_000))
    monkeypatch.setattr(manage.common_paths, "get_log_folder", lambda: logs)
    monkeypatch.setitem(library.settings, "logs_expire_time", 1)
    monkeypatch.setitem(library.settings, "rotate_logs", True)
    monkeypatch.setitem(library.settings, "dry_run", dry)

    manage.cleanup_logs()

    assert old.exists() is dry


def test_json_report(report_env, tmp_path):
    import json

    asyncio.run(dry_run.record("a creator", [media("Timeline", "Images", 1, url="https://x/1.jpg")]))
    out = tmp_path / "report.json"
    dry_run.write_json(out)
    assert json.loads(out.read_text(encoding="utf-8")) == dry_run.data()


def test_dry_run_json_implies_dry_run():
    params = {"dry_run_json": "report.json", "actions": ["download"]}
    check_dry_run(params)
    assert params["dry_run"] is True
    with pytest.raises(UsageError, match="--daemon"):
        check_dry_run({"dry_run_json": "r.json", "daemon": 5.0, "actions": ["download"]})


@pytest.mark.parametrize("dry", [True, False])
def test_naming_script_runs_only_outside_a_dry_run(monkeypatch, library, tmp_path, dry):
    import ofscraper.scripts.naming_script as naming

    script = tmp_path / "name.py"
    script.write_text("", encoding="utf-8")
    monkeypatch.setitem(library.settings, "naming_script", str(script))
    monkeypatch.setitem(library.settings, "dry_run", dry)
    ran = []

    async def async_run(*a, **k):
        ran.append(a)
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(naming, "async_run", async_run)
    try:
        ele = SimpleNamespace(
            username="a creator", model_id=5, value="free", modified_responsetype="Timeline",
            label_string="", id=7, post={}, date=None,
        )
        monkeypatch.setattr(naming, "Post", SimpleNamespace)  # a post, for the payload
        asyncio.run(naming.naming_script("dir", "file.jpg", ele))
    except Exception:
        pass  # only whether the script was started matters here
    assert bool(ran) is not dry


@pytest.mark.parametrize(
    "run_script",
    [
        lambda: after_download.after_download_action_script("a creator", []),
        lambda: after_like.after_like_action_script("a creator", []),
        lambda: final_script.final_script(),
    ],
    ids=["after_action_script (download)", "after_action_script (like)", "post_script"],
)
@pytest.mark.parametrize("dry", [True, False])
def test_scripts_run_only_outside_a_dry_run(monkeypatch, library, tmp_path, run_script, dry):
    script = tmp_path / "script.py"
    script.write_text("", encoding="utf-8")
    monkeypatch.setitem(library.settings, "after_action_script", str(script))
    monkeypatch.setitem(library.settings, "post_script", str(script))
    monkeypatch.setitem(library.settings, "command", "scraper")
    monkeypatch.setitem(library.settings, "dry_run", dry)
    models = SimpleNamespace(
        get_processed=lambda a: set(),
        get_unprocessed=lambda a: [],
        get_model=lambda name: {"username": name, "id": 5},
    )
    ran = []
    for module in (after_download, after_like, final_script):
        monkeypatch.setattr(module, "run", lambda *a, **k: ran.append(a))
        monkeypatch.setattr(
            module, "manager", SimpleNamespace(Manager=SimpleNamespace(current_model_manager=models))
        )
    run_script()
    assert bool(ran) is not dry


@pytest.mark.parametrize("dry", [True, False])
def test_leftover_part_files_are_kept_in_a_dry_run(monkeypatch, library, tmp_path, dry):
    part = tmp_path / "temp" / ".file.mp4.part"
    part.parent.mkdir()
    part.write_bytes(b"x")
    monkeypatch.setattr(paths.data, "get_TempDir", lambda *a, **k: str(part.parent))
    monkeypatch.setitem(library.settings, "auto_resume", False)
    monkeypatch.setitem(library.settings, "dry_run", dry)
    real_getattr = paths.of_env.getattr
    monkeypatch.setattr(
        paths.of_env, "getattr",
        lambda key, *a, **k: True if key == "BATCH_TEMPFILE_CLEANUP" else real_getattr(key, *a, **k),
    )
    paths.temp_cleanup()
    assert part.exists() is dry


def test_fansly_scans_everything_first_in_a_dry_run(monkeypatch, library):
    monkeypatch.setattr(pipeline.sites, "is_fansly", lambda: True)
    for name, value in {
        "command": "scraper", "actions": ["download"], "users_first": False, "text_only": False,
    }.items():
        monkeypatch.setitem(library.settings, name, value)
    monkeypatch.setitem(library.settings, "dry_run", False)
    assert pipeline.applies()
    monkeypatch.setitem(library.settings, "dry_run", True)
    assert not pipeline.applies()


def test_postgresql_is_refused(monkeypatch):
    import ofscraper.db.postgres as postgres

    monkeypatch.setattr(postgres, "enabled", lambda: True)
    assert "PostgreSQL" in dry_run.refuse_reason()
    monkeypatch.setattr(postgres, "enabled", lambda: False)
    assert dry_run.refuse_reason() is None


def test_a_refused_dry_run_stops_before_the_profiles_daemon(monkeypatch):
    """The refusal comes before the --profiles daemon starts, as it does
    before an ordinary run."""
    from types import SimpleNamespace

    import ofscraper.commands.scraper.multi_profile as multi_profile
    import ofscraper.main.open.run as run

    started = []
    monkeypatch.setattr(dry_run, "active", lambda: True)
    monkeypatch.setattr(dry_run, "refuse_reason", lambda: "refused")
    monkeypatch.setattr(settings, "get_args", lambda *a, **k: SimpleNamespace(profiles=["a", "b"]))
    monkeypatch.setattr(multi_profile, "run_multi_profile_daemon", started.append)
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == 2 and started == []


# --- refused combinations ---------------------------------------------------


@pytest.mark.parametrize(
    "params, message",
    [
        ({"daemon": 30.0, "actions": ["download"]}, "--daemon"),
        ({"live": True, "actions": ["download"]}, "--live"),
        ({"live_watch": True, "actions": ["download"]}, "--live"),
        ({"actions": ["like"]}, "--action download"),
        ({"actions": []}, "--action download"),
    ],
)
def test_refused_combinations(params, message):
    with pytest.raises(UsageError, match=message):
        check_dry_run({"dry_run": True, **params})


@pytest.mark.parametrize(
    "params",
    [
        {"actions": ["download"]},
        {"actions": ["like", "download"]},
        {"actions": [], "scrape_paid": True},
    ],
)
def test_accepted_combinations(params):
    check_dry_run({"dry_run": True, **params})
    check_dry_run({"dry_run": False, "daemon": 30.0, **params})


def test_option_parses():
    from ofscraper.utils.args.parse.commands.main import program

    ctx = program.make_context(
        "ofscraper", ["--dry-run", "--action", "download"], resilient_parsing=False
    )
    assert ctx.params["dry_run"] is True


@pytest.mark.parametrize(
    "subcommand", [["metadata", "--metadata", "check"], ["manual"], ["db"], ["post_check"]]
)
def test_dry_run_is_refused_with_a_subcommand(subcommand):
    # a subcommand doesn't run the scraper, so it wouldn't be a dry run at all
    import ofscraper.utils.args.parse.commands.db as db
    import ofscraper.utils.args.parse.commands.manual as manual
    import ofscraper.utils.args.parse.commands.metadata as metadata
    import ofscraper.utils.args.parse.commands.post as post
    from ofscraper.utils.args.parse.commands.main import program

    # the subcommands as parse_args() registers them
    for name, command in {
        "metadata": metadata.metadata, "manual": manual.manual, "db": db.db,
        "post_check": post.post_check,
    }.items():
        if name not in program.commands:
            program.add_command(command, name)
    with pytest.raises(UsageError, match=f"--dry-run can't be used with {subcommand[0]}"):
        program(
            standalone_mode=False, prog_name="OF-Scraper",
            args=["--dry-run", "--action", "download", *subcommand],
        )


def test_postgresql_is_refused_before_connecting(monkeypatch):
    # the refusal comes before the run connects to (and changes) the server
    import ofscraper.db.postgres as postgres
    import ofscraper.main.open.run as run

    monkeypatch.setattr(postgres, "enabled", lambda: True)
    monkeypatch.setattr(dry_run, "active", lambda: True)
    touched = []
    monkeypatch.setattr(postgres.POSTGRES, "check", lambda *a, **k: touched.append("check"))
    monkeypatch.setattr(run, "start_manager", lambda: touched.append("start"))
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == 2
    assert touched == []


# --- the end of a run ---------------------------------------------------------


def test_closing_the_cache_after_cleanup_makes_no_new_copy(library, monkeypatch):
    # shutdown closes the cache after the dry run removed its copy
    monkeypatch.setitem(library.settings, "dry_run", True)
    assert cache.get("scan_mark") == "real"
    dry_run.cleanup()
    cache.close()
    assert dry_run._root is None


def test_a_dry_run_leaves_the_database_lock_and_makes_no_folder(library, monkeypatch, tmp_path):
    monkeypatch.setitem(library.settings, "dry_run", True)
    lock = library.profile / "db.lock"
    lock.write_text("held")
    paths.cleanDB()
    assert lock.exists()
    missing = tmp_path / "cfg" / "other_profile"
    monkeypatch.setattr(common_paths, "get_profile_path", lambda *a, **k: missing)
    common_paths.getcachepath()
    assert not missing.exists()


@pytest.fixture
def scraper_run(monkeypatch, library, tmp_path):
    """scraper.main() with the scan replaced; the report is collected."""
    import ofscraper.commands.scraper.scraper as scraper

    reports = []
    monkeypatch.setattr(scraper.network, "check_cdm", lambda: None)
    monkeypatch.setattr(scraper, "print_start", lambda: None)
    monkeypatch.setattr(scraper.log, "traceback_", lambda *a: None, raising=False)
    monkeypatch.setattr(
        dry_run.log, "warning",
        lambda msg, *a, **k: reports.append(msg) if msg.startswith("Dry run:") else None,
    )
    monkeypatch.setitem(library.settings, "dry_run", True)
    monkeypatch.setitem(library.settings, "dry_run_json", str(tmp_path / "report.json"))
    for name in ("size_max", "size_min", "skip_download_script"):
        monkeypatch.setitem(library.settings, name, None)
    return SimpleNamespace(scraper=scraper, reports=reports, json=tmp_path / "report.json")


def test_no_report_when_the_scan_fails(scraper_run, monkeypatch):
    def scan():
        asyncio.run(dry_run.record("a creator", [media("Timeline", "Images", 1)]))
        raise RuntimeError("auth failed")

    monkeypatch.setattr(scraper_run.scraper, "scrapper", scan)
    with pytest.raises(RuntimeError):
        scraper_run.scraper.main()
    assert scraper_run.reports == []
    assert not scraper_run.json.exists()
    assert dry_run._root is None  # the copies were still removed


def test_each_pass_of_the_action_loop_has_its_own_report(scraper_run, monkeypatch):
    scraper = scraper_run.scraper

    class Manager:
        def runner(self):
            # each pass sees the real database, not the last pass's copy
            copy = placeholder.databasePlaceholder().databasePathHelper(5, "a creator")
            assert media_ids(copy) == [1]
            with contextlib.closing(sqlite3.connect(copy)) as conn:
                conn.execute("DELETE FROM medias")
                conn.commit()
            asyncio.run(dry_run.record("a creator", [media("Timeline", "Videos", 1)]))

    answers = iter(["Yes", "No"])
    monkeypatch.setattr(scraper, "scraperManager", Manager)
    monkeypatch.setattr(scraper.data, "get_InfiniteLoop", lambda: True)
    monkeypatch.setattr(scraper.prompts, "continue_prompt", lambda: next(answers))
    monkeypatch.setattr(scraper.prompts, "action_prompt", lambda: "download")
    monkeypatch.setattr(scraper.menu, "get_count", lambda: 0)
    monkeypatch.setattr(scraper.menu, "update_count", lambda: None)
    monkeypatch.setattr(scraper, "scrapper", scraper.process_selected_areas)
    scraper.main()
    assert len(scraper_run.reports) == 2
    for text in scraper_run.reports:
        assert "1 video)" in text
        assert "up to 1 file from 1 creator" in text


# --- second review round -------------------------------------------------------


def test_a_failed_scan_leaves_no_counts_for_the_next_report(scraper_run, monkeypatch):
    def scan():
        asyncio.run(dry_run.record("a creator", [media("Timeline", "Images", 1)]))
        raise RuntimeError("auth failed")

    monkeypatch.setattr(scraper_run.scraper, "scrapper", scan)
    with pytest.raises(RuntimeError):
        scraper_run.scraper.main()
    assert dry_run.data()["creators"] == []


def test_the_action_loop_offers_no_menu_or_check_table_in_a_dry_run(library, monkeypatch):
    import ofscraper.prompts.prompt_groups.actions as actions_prompt

    args = SimpleNamespace(daemon=None, site="onlyfans")
    monkeypatch.setattr(actions_prompt.sites, "is_fansly", lambda: False)
    names = [c for c in actions_prompt.action_menu_choices(args) if isinstance(c, str)]
    assert "Go to main menu" in names and "Browse and pick media (check table)" in names
    monkeypatch.setitem(library.settings, "dry_run", True)
    names = [c for c in actions_prompt.action_menu_choices(args) if isinstance(c, str)]
    # the main menu and the check table change things for real
    assert "Go to main menu" not in names
    assert "Browse and pick media (check table)" not in names
    assert "Download content from a user" in names and "Quit" in names
