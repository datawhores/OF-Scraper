"""ofscraper doctor: offline checks of the setup, in a scratch home."""

import json
import os
import sys

import pytest

import ofscraper.__main__ as entrypoint
import ofscraper.commands.doctor as doctor
import ofscraper.db.postgres as postgres
import ofscraper.utils.system.ffmpeg as ffmpeg

SECRET = "s3cret-value-that-must-not-show-0123456789"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) a test agent"


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv(postgres.URL_KEY, raising=False)
    monkeypatch.delenv("OFSC_FFMPEG_DEFAULT", raising=False)
    return home


def config_dir(home):
    return home / ".config" / "ofscraper"


def write_config(home, config):
    path = config_dir(home) / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config) if not isinstance(config, str) else config, encoding="utf-8")
    return path


def write_auth(home, **fields):
    auth = {"sess": SECRET, "auth_id": "12345", "user_agent": UA, "x-bc": SECRET, **fields}
    path = config_dir(home) / "main_profile" / "auth.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"auth": auth}), encoding="utf-8")
    return path


def result(report, check):
    (found,) = [r for r in report.results if r["check"] == check]
    return found["status"], found["detail"]


def files_under(path):
    return sorted(str(p) for p in path.rglob("*"))


def test_an_empty_home_gets_findings_and_nothing_is_created(home):
    report = doctor.run()
    assert files_under(home) == []
    assert result(report, "config file")[0] == "WARN"
    assert result(report, "OnlyFans auth") == (
        "WARN", f"{os.path.join('~', '.config', 'ofscraper', 'main_profile', 'auth.json')} isn't there: a run asks for the login and makes it")
    assert result(report, "Fansly auth")[0] == "SKIP"


def test_a_fresh_install_fails_only_what_a_run_cant_fix_itself(home):
    """No config, no auth file and no save folder are what a first run
    meets: it makes the config and the folder and asks for the login. In
    the default manual key mode, no key files yet is a warning: the run
    goes on and skips the protected videos."""
    report = doctor.run()
    failed = {r["check"] for r in report.results if r["status"] == "FAIL"}
    assert failed <= {"ffmpeg"}
    status, detail = result(report, "key files")
    assert status == "WARN" and "videos are skipped until" in detail
    assert result(report, "save folder")[0] == "WARN"
    assert result(report, "OnlyFans auth")[0] == "WARN"


def test_online_without_an_auth_file_skips_the_login_and_never_prompts(home, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("asked a question"))
    monkeypatch.setattr(doctor, "start", lambda *a: pytest.fail("started"))
    status, detail = result(doctor.run(online=True), "Onlyfans login")
    assert status == "SKIP" and "no auth file yet" in detail


def test_the_home_folder_and_login_name_arent_printed(home, tmp_path, monkeypatch, capsys):
    """The output is pasted into public issues: the home folder is ~ and the
    login name doesn't show where it's a folder name outside it."""
    monkeypatch.setattr(doctor.getpass, "getuser", lambda: "someuser")
    elsewhere = tmp_path / "disk" / "someuser" / "media"
    write_config(home, {"advanced_options": {"temp_dir": str(elsewhere)}})
    doctor.main([])
    doctor.main(["--json"])
    out = capsys.readouterr().out
    assert str(home) not in out and str(home).replace("\\", "/") not in out
    assert "someuser" not in out
    assert os.path.join("~", ".config", "ofscraper", "config.json") in out
    assert os.path.join("<user>", "media") in out


def test_a_broken_config_is_a_finding_not_a_prompt(home, monkeypatch):
    write_config(home, '{\n  "main_profile": "main_profile",\n  oops\n}')
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("asked a question"))
    status, detail = result(doctor.run(), "config file")
    assert status == "FAIL" and "line 3" in detail


def test_a_config_startup_rejects_fails_even_when_it_could_be_repaired(home, monkeypatch):
    # an unescaped Windows path: the run stops at it and asks for a fix, so
    # doctor mustn't pass it by repairing the backslashes first
    write_config(home, '{\n  "main_profile": "main_profile",\n  "save_location": "D:\\Media\\OF"\n}')
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("asked a question"))
    status, detail = result(doctor.run(), "config file")
    assert status == "FAIL" and "line 3" in detail and "Media" not in detail


def test_auth_fields_are_named_never_shown(home, capsys):
    write_config(home, {"main_profile": "main_profile"})
    write_auth(home, **{"x-bc": ""})
    status, detail = result(doctor.run(), "OnlyFans auth")
    assert status == "FAIL" and detail.endswith("blank in " + os.path.join("~", ".config", "ofscraper", "main_profile", "auth.json") + ": x-bc")
    write_auth(home)
    assert result(doctor.run(), "OnlyFans auth")[0] == "PASS"
    doctor.main([])
    doctor.main(["--json"])
    out = capsys.readouterr().out
    assert SECRET not in out and UA not in out


def test_a_fansly_profile_checks_the_fansly_auth(home):
    folder = config_dir(home) / "main_profile"
    folder.mkdir(parents=True)
    (folder / "site.json").write_text('{"site": "fansly"}', encoding="utf-8")
    report = doctor.run()
    assert result(report, "OnlyFans auth")[0] == "SKIP"
    status, detail = result(report, "Fansly auth")
    assert status == "WARN" and "isn't there: a run asks for the login" in detail
    (folder / "fansly_auth.json").write_text(json.dumps({"authorization_token": "x" * 60, "user_agent": UA}), encoding="utf-8")
    assert result(doctor.run(), "Fansly auth")[0] == "PASS"
    (folder / "fansly_auth.json").write_text(json.dumps({"authorization_token": "short", "user_agent": UA}), encoding="utf-8")
    status, detail = result(doctor.run(), "Fansly auth")
    assert status == "FAIL" and "authorization_token is missing or too short" in detail


def test_an_old_configured_ffmpeg_fails(home, monkeypatch, tmp_path):
    fake = tmp_path / "ffmpeg.exe"
    fake.write_bytes(b"")
    write_config(home, {"binary_options": {"ffmpeg": str(fake)}})
    monkeypatch.setattr(doctor.shutil, "which", lambda p: p)
    monkeypatch.setattr(ffmpeg, "ffmpeg_version", lambda p: (True, "5.1.2", 5))
    assert result(doctor.run(), "ffmpeg") == ("FAIL", f"{doctor.redact(str(fake))} is version 5.1.2; protected videos need 6 or newer")


def test_ffmpeg_shows_its_version_and_where_it_was_found(home, monkeypatch):
    monkeypatch.setattr(ffmpeg, "find_ffmpeg", lambda configured: ("/usr/bin/ffmpeg", "PATH", "7.1"))
    assert result(doctor.run(), "ffmpeg") == ("PASS", "7.1 (from PATH): /usr/bin/ffmpeg")
    monkeypatch.setattr(ffmpeg, "find_ffmpeg", lambda configured: (None, None, None))
    report = doctor.run()
    assert result(report, "ffmpeg")[0] == "FAIL" and result(report, "ffprobe")[0] == "SKIP"


def test_ffmpeg_version_reads_the_version(monkeypatch):
    class Done:
        stdout = "ffmpeg version 7.1.1-essentials Copyright (c) 2000-2025\n"
        stderr = ""

    monkeypatch.setattr(ffmpeg, "run", lambda *a, **k: Done)
    assert ffmpeg.ffmpeg_version("ffmpeg") == (True, "7.1.1-essentials", 7)
    Done.stdout = "ffmpeg version N-118000-gabc Copyright"
    assert ffmpeg.ffmpeg_version("ffmpeg") == (True, "N-118000-gabc", None)
    Done.stdout = "something else"
    assert ffmpeg.ffmpeg_version("ffmpeg") == (False, None, None)


def test_key_files(home, tmp_path):
    write_config(home, {"cdm_options": {"key-mode-default": "manual"}})
    status, detail = result(doctor.run(), "key files")
    assert status == "WARN" and detail.startswith("no key files set up yet")
    client, key = tmp_path / "client_id.bin", tmp_path / "private_key.pem"
    # half set up is a mistake in what was configured, not the default
    write_config(home, {"cdm_options": {"key-mode-default": "manual", "client-id": str(client)}})
    status, detail = result(doctor.run(), "key files")
    assert status == "FAIL" and "private-key is not set" in detail
    write_config(home, {"cdm_options": {"key-mode-default": "manual", "client-id": str(client), "private-key": str(key)}})
    status, detail = result(doctor.run(), "key files")
    assert status == "FAIL" and "file not found" in detail
    client.write_bytes(b"not a client id")
    key.write_bytes(b"not a key")
    status, detail = result(doctor.run(), "key files")
    assert status == "FAIL" and detail.startswith("the key files can't be loaded")
    write_config(home, {"cdm_options": {"key-mode-default": "cdrm"}})
    assert "isn't contacted" in result(doctor.run(), "key files")[1]


@pytest.mark.parametrize(
    "windows,save,said",
    [
        # Linux and macOS: nothing there below a place drives are mounted
        (False, ("mnt", "nas", "OF"), "FAIL"),
        (False, ("run-media", "someone", "disk", "OF"), "FAIL"),
        # a folder that isn't a mount place: a run makes the rest
        (False, ("data", "new", "OF"), "WARN"),
        # Windows: the drive is there, so a run makes the folder
        (True, ("mnt", "nas", "OF"), "WARN"),
    ],
)
def test_a_save_folder_on_a_drive_that_isnt_mounted_fails(home, tmp_path, monkeypatch, windows, save, said):
    # tmp_path/mnt and tmp_path/run-media stand in for /mnt and /run/media
    for folder in ("mnt", "run-media/someone", "data"):
        (tmp_path / folder).mkdir(parents=True)
    monkeypatch.setattr(doctor, "_windows", lambda: windows)
    monkeypatch.setattr(doctor, "MOUNT_PARENTS", (str(tmp_path / "mnt"),))
    monkeypatch.setattr(doctor, "USER_MOUNT_PARENTS", (str(tmp_path / "run-media"),))
    save = tmp_path.joinpath(*save)
    write_config(home, {"file_options": {"save_location": str(save)}})
    status, detail = result(doctor.run(), "save folder")
    assert status == said
    if said == "FAIL":
        assert detail.endswith("isn't there: is the drive or share mounted?")
    else:
        assert detail.endswith("isn't there yet: a run makes it")


def test_folders_and_the_free_space_limit(home, tmp_path, monkeypatch):
    save = tmp_path / "library"
    write_config(home, {"file_options": {"save_location": str(save)}, "download_options": {"system_free_min": 1000}})
    report = doctor.run()
    assert result(report, "save folder") == ("WARN", f"{doctor.redact(str(save))} isn't there yet: a run makes it")
    save.mkdir()
    # of_env reads OFSC_DISK_SPACE_CHECK_PATH once, so the value is given here
    check_path = {"value": str(save)}
    real_getattr = doctor.of_env.getattr
    monkeypatch.setattr(doctor.of_env, "getattr",
                        lambda key, *a, **k: check_path["value"] if key == "DISK_SPACE_CHECK_PATH" else real_getattr(key, *a, **k))
    report = doctor.run()
    assert result(report, "save folder")[0] == "PASS"
    assert result(report, "free-space limit")[1].startswith(f"1000 bytes, measured at {doctor.redact(str(save))}")
    real = doctor._device
    monkeypatch.setattr(doctor, "_device", lambda p: 1 if str(p) == str(save) else real(p) and 2)
    check_path["value"] = str(tmp_path)
    status, detail = result(doctor.run(), "free-space limit")
    assert status == "WARN" and "OFSC_DISK_SPACE_CHECK_PATH" in detail


def test_a_temp_folder_that_isnt_there(home, tmp_path):
    write_config(home, {"advanced_options": {"temp_dir": str(tmp_path / "nope")}})
    assert result(doctor.run(), "temp folder")[0] == "FAIL"


def test_database_setting_is_named_without_the_password(home, monkeypatch, capsys):
    monkeypatch.setenv(postgres.URL_KEY, f"postgresql://scraper:{SECRET}@db.example:5432/library")
    monkeypatch.setitem(sys.modules, "psycopg", None)
    status, detail = result(doctor.run(), "database")
    assert status == "FAIL" and "driver" in detail and SECRET not in detail
    doctor.main(["--json"])
    assert SECRET not in capsys.readouterr().out


def test_routed_with_exit_status_and_json(home, capsys, monkeypatch):
    monkeypatch.setattr(ffmpeg, "find_ffmpeg", lambda configured: (None, None, None))
    assert entrypoint.main(["doctor", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert {r["status"] for r in report["results"]} <= {"PASS", "WARN", "FAIL", "SKIP"}
    assert files_under(home) == []


def test_config_path_follows_the_runs_rule(home, tmp_path):
    folder = tmp_path / "cfg"
    folder.mkdir()
    assert doctor.config_path(str(folder)) == folder / "config.json"
    assert doctor.config_path("other.json") == config_dir(home) / "other.json"
    assert doctor.config_path(None) == config_dir(home) / "config.json"
    assert os.path.basename(doctor.config_path(str(tmp_path / "x" / "my.json"))) == "my.json"


# --- --online ---

def test_online_with_a_blank_auth_file_skips_the_login_and_never_prompts(home, monkeypatch):
    write_config(home, {"main_profile": "main_profile"})
    write_auth(home, sess="")
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("asked a question"))
    monkeypatch.setattr(doctor, "start", lambda *a: pytest.fail("started"))
    status, detail = result(doctor.run(online=True), "Onlyfans login")
    assert status == "SKIP" and "auth file failed" in detail


def test_online_reports_postgresql_down_and_goes_on(home, monkeypatch):
    import ofscraper.data.api.init as init

    monkeypatch.setenv(postgres.URL_KEY, f"postgresql://scraper:{SECRET}@db.example:5432/library")
    monkeypatch.setitem(sys.modules, "psycopg", sys.modules.get("psycopg") or object())
    monkeypatch.setitem(sys.modules, "psycopg_pool", sys.modules.get("psycopg_pool") or object())

    def down():
        raise postgres.PostgresUnavailable("Can't use the PostgreSQL database at db.example:5432/library")

    monkeypatch.setattr(postgres.POSTGRES, "check", down)
    write_config(home, {"main_profile": "main_profile"})
    write_auth(home)
    monkeypatch.setattr(doctor, "start", lambda *a: None)
    monkeypatch.setattr(init, "auth_status", lambda: ("UP", None))
    report = doctor.run(online=True)
    assert result(report, "PostgreSQL")[0] == "FAIL"
    assert result(report, "Onlyfans login") == ("PASS", "logged in")
    assert SECRET not in json.dumps(report.results)


@pytest.mark.parametrize("answer, status", [
    (("DOWN", None), "FAIL"),
    (("UNAVAILABLE", "couldn't reach the site"), "WARN"),
])
def test_online_tells_a_rejected_login_from_one_not_checked(home, monkeypatch, answer, status):
    import ofscraper.data.api.init as init

    write_config(home, {"main_profile": "main_profile"})
    write_auth(home)
    monkeypatch.setattr(doctor, "start", lambda *a: None)
    monkeypatch.setattr(init, "auth_status", lambda: answer)
    assert result(doctor.run(online=True), "Onlyfans login")[0] == status


def test_online_says_which_signing_rule_source_answered(home, monkeypatch):
    import ofscraper.data.api.init as init
    import ofscraper.utils.auth.request as request

    write_config(home, {"main_profile": "main_profile"})
    write_auth(home)
    monkeypatch.setattr(doctor, "start", lambda *a: None)
    monkeypatch.setattr(init, "auth_status", lambda: ("UP", None))
    monkeypatch.setattr(request, "last_attempt", {"used": "rafa", "failed": [("xagler", "couldn't reach the rule host (timed out)")]})
    status, detail = result(doctor.run(online=True), "signing rules")
    assert status == "WARN" and "from rafa" in detail and "xagler" in detail


def test_online_stash_unreachable(home, monkeypatch):
    monkeypatch.setenv("STASH_URL", "http://127.0.0.1:9/graphql")
    monkeypatch.setenv("STASH_API_KEY", SECRET)
    write_config(home, {"main_profile": "main_profile"})
    report = doctor.run(online=True)
    status, detail = result(report, "Stash")
    assert status == "FAIL" and SECRET not in detail


def test_offline_points_at_online(home):
    assert result(doctor.run(), "login")[0] == "SKIP"


# --- review follow-up ---

def test_online_postgres_check_parses_no_command_line(home, monkeypatch, capsys):
    """The PostgreSQL check runs before the start sets sys.argv: reading the
    settings there would parse `doctor --online` as a run's options."""
    import types

    import ofscraper.data.api.init as init
    import ofscraper.utils.args.globals as global_args
    import ofscraper.utils.settings as settings

    monkeypatch.setenv(postgres.URL_KEY, f"postgresql://scraper:{SECRET}@db.example:5432/library")
    monkeypatch.setitem(sys.modules, "psycopg", sys.modules.get("psycopg") or object())
    monkeypatch.setitem(sys.modules, "psycopg_pool", sys.modules.get("psycopg_pool") or object())
    monkeypatch.setattr(sys, "argv", ["ofscraper", "doctor", "--online", "--json"])
    monkeypatch.setattr(settings, "settings", {})
    monkeypatch.setattr(global_args, "args", None)
    schemas = []
    conn = types.SimpleNamespace(info=types.SimpleNamespace(server_version=160002))
    monkeypatch.setattr(postgres.POSTGRES, "connect", lambda where, ro, timeout: schemas.append(where) or conn)
    monkeypatch.setattr(postgres.POSTGRES, "close", lambda c: None)
    monkeypatch.setattr(doctor, "start", lambda *a: None)
    monkeypatch.setattr(init, "auth_status", lambda: ("UP", None))
    write_config(home, {"main_profile": "main_profile"})
    write_auth(home)
    entrypoint.main(["doctor", "--online", "--json"])
    results = {r["check"]: r for r in json.loads(capsys.readouterr().out)["results"]}
    assert results["PostgreSQL"]["status"] == "PASS" and "16.2" in results["PostgreSQL"]["detail"]
    assert schemas == ["onlyfans"]
    assert settings.settings == {} and global_args.args is None


def test_an_empty_auth_file_is_a_finding(home, monkeypatch):
    import ofscraper.utils.settings as settings

    write_config(home, {"main_profile": "main_profile"})
    path = write_auth(home)
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "get_settings", lambda: pytest.fail("read the settings"))
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("asked a question"))
    assert result(doctor.run(), "OnlyFans auth") == ("FAIL", f"{doctor.redact(str(path))} is empty")


def test_an_empty_config_object_is_the_defaults(home, monkeypatch):
    import ofscraper.utils.config.file as config_file
    import ofscraper.utils.settings as settings

    write_config(home, {})
    monkeypatch.setattr(config_file, "open_config", lambda: pytest.fail("opened the config"))
    monkeypatch.setattr(settings, "get_args", lambda *a, **k: pytest.fail("read the arguments"))
    report = doctor.run()
    assert result(report, "config file")[0] == "PASS"
    assert result(report, "save folder")[0] in ("PASS", "WARN")


def test_an_unset_check_path_measures_the_save_folders_disk(home, tmp_path, monkeypatch):
    """OFSC_DISK_SPACE_CHECK_PATH empty means the disk that holds
    save_location, as the free-space check measures it."""
    save = tmp_path / "library"
    save.mkdir()
    write_config(home, {"file_options": {"save_location": str(save / "not" / "made")},
                        "download_options": {"system_free_min": 1000}})
    real = doctor.of_env.getattr
    # an empty value is what the default becomes with #795
    monkeypatch.setattr(doctor.of_env, "getattr",
                        lambda key, *a, **k: "" if key == "DISK_SPACE_CHECK_PATH" else real(key, *a, **k))
    status, detail = result(doctor.run(), "free-space limit")
    assert status == "PASS" and detail.startswith(f"1000 bytes, measured at {doctor.redact(str(save))}")


def test_a_fansly_profile_needs_no_key_files(home):
    write_config(home, {"cdm_options": {"key-mode-default": "manual"}})
    folder = config_dir(home) / "main_profile"
    folder.mkdir(parents=True)
    (folder / "site.json").write_text('{"site": "fansly"}', encoding="utf-8")
    assert result(doctor.run(), "key files")[0] == "SKIP"


@pytest.mark.parametrize("fields, named", [
    ({"sess": "   "}, "blank in"),
    ({"auth_id": 12345}, "not text in"),
    ({"x-bc": None}, "blank in"),
])
def test_auth_values_a_run_cant_use_fail_offline(home, fields, named):
    write_config(home, {"main_profile": "main_profile"})
    write_auth(home, **fields)
    status, detail = result(doctor.run(), "OnlyFans auth")
    assert status == "FAIL" and named in detail and detail.endswith(next(iter(fields)))


def test_an_ansi_config_and_auth_file_are_read(home, tmp_path, monkeypatch):
    import locale

    save = tmp_path / "Bibliothèque"
    save.mkdir()
    monkeypatch.setattr(locale, "getencoding", lambda: "cp1252")
    path = write_config(home, "")
    path.write_bytes(json.dumps({"file_options": {"save_location": str(save)}}, ensure_ascii=False).encode("cp1252"))
    auth = write_auth(home)
    auth.write_bytes(auth.read_bytes().replace(b"a test agent", "agent é".encode("cp1252")))
    report = doctor.run()
    assert result(report, "config file")[0] == "PASS"
    assert result(report, "save folder")[0] == "PASS"
    assert result(report, "OnlyFans auth")[0] == "PASS"


def test_a_working_configured_ffmpeg_doesnt_ask_pyffmpeg(monkeypatch):
    class Pyffmpeg:
        def FFmpeg(self):
            pytest.fail("asked pyffmpeg")

    monkeypatch.setitem(sys.modules, "pyffmpeg", Pyffmpeg())
    monkeypatch.setattr(ffmpeg, "_is_valid_ffmpeg", lambda p: p == "/opt/ffmpeg")
    monkeypatch.setattr(ffmpeg, "ffmpeg_version", lambda p: (True, "7.1", 7))
    assert ffmpeg.find_ffmpeg("/opt/ffmpeg") == ("/opt/ffmpeg", "config", "7.1")


def fake_pyffmpeg(tmp_path, monkeypatch):
    """An installed pyffmpeg that, like the real one, writes under the home
    folder as soon as it is imported."""
    package = tmp_path / "site" / "pyffmpeg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "import os, pathlib\n"
        "folder = pathlib.Path(os.environ['USERPROFILE' if os.name == 'nt' else 'HOME'], '.pyffmpeg', 'bin')\n"
        "folder.mkdir(parents=True, exist_ok=True)\n"
        "class FFmpeg:\n"
        "    def get_ffmpeg_bin(self):\n"
        "        (folder / 'ffmpeg').write_bytes(b'unpacked')\n"
        "        return str(folder / 'ffmpeg')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(package.parent))
    monkeypatch.delitem(sys.modules, "pyffmpeg", raising=False)


def test_pyffmpeg_is_found_without_unpacking_it(home, tmp_path, monkeypatch):
    fake_pyffmpeg(tmp_path, monkeypatch)
    status, detail = result(doctor.run(), "ffmpeg")
    assert files_under(home) == []
    assert "pyffmpeg" not in sys.modules
    assert status == "PASS" and "not unpacked yet" in detail and os.path.join("~", ".pyffmpeg", "bin") in detail


def test_an_unpacked_pyffmpeg_is_checked_where_it_is(home, tmp_path, monkeypatch):
    fake_pyffmpeg(tmp_path, monkeypatch)
    _installed, bundled = ffmpeg.pyffmpeg_bin()
    os.makedirs(os.path.dirname(bundled))
    open(bundled, "wb").close()
    monkeypatch.setattr(ffmpeg, "_is_valid_ffmpeg", lambda p: p == bundled)
    monkeypatch.setattr(ffmpeg, "ffmpeg_version", lambda p: (True, "7.1", 7))
    assert ffmpeg.find_ffmpeg(None) == (bundled, "pyffmpeg", "7.1")
    assert "pyffmpeg" not in sys.modules


def test_online_json_is_the_only_thing_on_stdout(home, monkeypatch, capsys):
    import ofscraper.data.api.init as init

    write_config(home, {"main_profile": "main_profile"})
    write_auth(home)
    monkeypatch.setattr(doctor, "start", lambda *a: print("a config was made"))
    monkeypatch.setattr(init, "auth_status", lambda: ("UP", None))
    doctor.main(["--online", "--json"])
    captured = capsys.readouterr()
    assert json.loads(captured.out)["results"]
    assert "a config was made" in captured.err


# --- second review round ---

@pytest.mark.parametrize("reply", ["{}", "[]", '{"data": {"version": "x"}}', '{"errors": ["x"]}'])
def test_online_stash_with_an_odd_reply_is_a_finding(home, monkeypatch, reply):
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            body = reply.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("STASH_URL", f"http://127.0.0.1:{server.server_port}/graphql")
        report = doctor.Report()
        doctor.check_stash(report)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    status, detail = result(report, "Stash")
    assert status == "FAIL" and "unexpected reply" in detail


@pytest.mark.parametrize("text", ["null", "123", "true"])
def test_an_auth_file_holding_null_or_a_number_is_a_finding(home, text):
    write_config(home, {"main_profile": "main_profile"})
    path = write_auth(home)
    path.write_text(text, encoding="utf-8")
    assert result(doctor.run(), "OnlyFans auth")[0] == "FAIL"


def test_free_space_that_cant_be_read_is_a_finding_not_a_crash(home, tmp_path, monkeypatch):
    save = tmp_path / "library"
    save.mkdir()
    write_config(home, {"file_options": {"save_location": str(save)}})
    real = doctor.shutil.disk_usage

    def disk_usage(path):
        if str(path) == str(save):
            raise PermissionError(13, "Permission denied")
        return real(path)

    monkeypatch.setattr(doctor.shutil, "disk_usage", disk_usage)
    status, detail = result(doctor.run(), "save folder")
    assert status == "PASS" and "free space can't be read" in detail


def test_a_linked_save_folder_is_measured_on_the_links_target(home, tmp_path, monkeypatch):
    """As #795's free-space check: a link is followed first, even to a
    folder that's missing, so the disk measured is the target's."""
    target = tmp_path / "other_disk"
    target.mkdir()
    links = tmp_path / "links"
    links.mkdir()
    save = links / "library"
    try:
        save.symlink_to(target / "not" / "made", target_is_directory=True)
    except OSError:
        pytest.skip("can't make a symbolic link here")
    write_config(home, {"file_options": {"save_location": str(save)},
                        "download_options": {"system_free_min": 1000}})
    real = doctor.of_env.getattr
    monkeypatch.setattr(doctor.of_env, "getattr",
                        lambda key, *a, **k: "" if key == "DISK_SPACE_CHECK_PATH" else real(key, *a, **k))
    status, detail = result(doctor.run(), "free-space limit")
    assert detail.startswith(f"1000 bytes, measured at {doctor.redact(str(target.resolve()))},")
