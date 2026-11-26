"""ofscraper doctor: offline checks of the setup, in a scratch home."""

import json
import os
import pathlib
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


def command_on_path(tmp_path, monkeypatch, content):
    folder = tmp_path / "bin"
    folder.mkdir()
    script = folder / ("ofscraper.exe" if os.name == "nt" else "ofscraper")
    script.write_bytes(content)
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(folder))
    return script


def test_the_first_line_names_the_running_install(home):
    from ofscraper.__version__ import __version__

    first = doctor.run().results[0]
    assert first["check"] == "install" and first["status"] == "PASS"
    assert __version__ in first["detail"] and doctor.redact(sys.executable) in first["detail"]
    assert doctor.redact(str(pathlib.Path(doctor.__file__).resolve().parents[1])) in first["detail"]


def test_ofscraper_on_path_from_this_install_passes(home, tmp_path, monkeypatch):
    script = command_on_path(tmp_path, monkeypatch, f"#!{sys.executable}\nimport ofscraper\n".encode())
    assert passes_as_this_install(script)


def passes_as_this_install(script):
    # Windows finds ofscraper.exe as ofscraper.EXE, the case PATHEXT gives
    status, detail = result(doctor.run(), "ofscraper on PATH")
    return status == "PASS" and os.path.normcase(detail) == os.path.normcase(f"{doctor.redact(str(script))}, this install")


def test_ofscraper_on_path_from_another_install_warns(home, tmp_path, monkeypatch):
    other = str(tmp_path / "pipx" / "venvs" / "ofscraper" / "bin" / "python")
    script = command_on_path(tmp_path, monkeypatch, f"#!{other}\nimport ofscraper\n".encode())
    status, detail = result(doctor.run(), "ofscraper on PATH")
    assert status == "WARN" and os.path.normcase(doctor.redact(str(script))) in os.path.normcase(detail)
    assert doctor.redact(sys.executable) in detail
    # pip's form for a long path
    script.write_bytes(f"#!/bin/sh\n'''exec' \"{other}\" \"$0\" \"$@\"\n' '''\n".encode())
    assert result(doctor.run(), "ofscraper on PATH")[0] == "WARN"
    script.write_bytes(f"#!/bin/sh\n'''exec' \"{sys.executable}\" \"$0\" \"$@\"\n' '''\n".encode())
    assert result(doctor.run(), "ofscraper on PATH")[0] == "PASS"


def installed_command(tmp_path, name, python):
    """An ofscraper command an install made, outside PATH."""
    folder = tmp_path / name / "bin"
    folder.mkdir(parents=True)
    command = folder / "ofscraper"
    command.write_bytes(f"#!{python}\nimport ofscraper\n".encode())
    return command


@pytest.mark.parametrize("wrapper", [
    '#!/bin/sh\nexec "{command}" "$@"\n',
    '#!/usr/bin/env bash\n# my wrapper\nset -e\nexec {command} --no-rich "$@"\n',
    '#!/bin/bash\nexec "{python}" -m ofscraper "$@"\n',
])
def test_a_shell_wrapper_that_runs_this_install_passes(home, tmp_path, monkeypatch, wrapper):
    command = installed_command(tmp_path, "venv", sys.executable)
    command_on_path(tmp_path, monkeypatch, wrapper.format(command=command.as_posix(), python=sys.executable).encode())
    status, detail = result(doctor.run(), "ofscraper on PATH")
    assert status == "PASS" and detail.endswith(", this install")


def test_a_shell_wrapper_that_runs_another_install_warns(home, tmp_path, monkeypatch):
    other = str(tmp_path / "pipx" / "venvs" / "ofscraper" / "bin" / "python")
    command = installed_command(tmp_path, "other", other)
    command_on_path(tmp_path, monkeypatch, f'#!/bin/sh\nexec "{command}" "$@"\n'.encode())
    assert result(doctor.run(), "ofscraper on PATH")[0] == "WARN"


def test_a_shim_doctor_cant_follow_isnt_called_another_install(home, tmp_path, monkeypatch):
    # a version manager's shim: the program it runs is only known at run time
    shim = '#!/usr/bin/env bash\nset -e\nprogram="${0##*/}"\nexec "/opt/manager/libexec/manager" exec "$program" "$@"\n'
    command_on_path(tmp_path, monkeypatch, shim.encode())
    status, detail = result(doctor.run(), "ofscraper on PATH")
    assert status == "SKIP" and "can't tell" in detail


def test_the_install_lines_show_the_home_folder_as_tilde(home, tmp_path, monkeypatch):
    fake_home = pathlib.Path(sys.executable).parents[1]
    monkeypatch.setattr(doctor.pathlib.Path, "home", classmethod(lambda cls: fake_home))
    install = doctor.run().results[0]["detail"]
    assert str(fake_home) not in install and f"~{os.sep}" in install


def test_no_ofscraper_on_path(home, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert result(doctor.run(), "ofscraper on PATH")[0] == "SKIP"


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


@pytest.mark.parametrize("fields, finding", [
    ({"sess": SECRET + ";"}, "sess has ;"),
    ({"auth_id": "123\u200b45"}, "auth_id has characters outside printable ASCII"),
    ({"x-bc": '"' + SECRET + '"'}, "x-bc has quotes"),
    ({"sess": "sess=" + SECRET}, "sess has ="),
    ({"user_agent": "Mozilla/5.0\u00a0(Windows NT 10.0)"}, "user_agent has characters outside printable ASCII"),
    ({"sess": "deleted"}, "sess is \"deleted\""),
    ({"sess": "Deleted"}, "sess is \"deleted\""),
    ({"sess": "DELETED"}, "sess is \"deleted\""),
])
def test_stray_characters_in_auth_fields_are_named_never_shown(home, fields, finding):
    write_config(home, {"main_profile": "main_profile"})
    write_auth(home, **fields)
    report = doctor.run()
    assert result(report, "OnlyFans auth")[0] == "PASS"
    status, detail = result(report, "OnlyFans auth values")
    assert status == "WARN" and finding in detail
    assert SECRET not in json.dumps(report.results) and "\u200b" not in detail


def test_clean_auth_fields_and_a_user_agents_semicolons_pass(home):
    write_config(home, {"main_profile": "main_profile"})
    write_auth(home, sess="  " + SECRET + "\n")
    report = doctor.run()
    assert [r for r in report.results if r["check"] in ("OnlyFans auth values", "auth in config")] == []


def test_auth_values_in_config_json(home):
    write_config(home, {"main_profile": "main_profile", "sess": SECRET, "general": {"x-bc": SECRET, "auth_id": ""}})
    write_auth(home)
    status, detail = result(doctor.run(), "auth in config")
    assert status == "WARN" and "sess, x-bc" in detail and "belong in auth.json" in detail
    assert SECRET not in detail


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


def manual_keys(home, client, key):
    write_config(home, {"cdm_options": {"key-mode-default": "manual", "client-id": str(client), "private-key": str(key)}})
    return result(doctor.run(), "key files")


def test_key_files_say_a_tilde_isnt_expanded(home, tmp_path):
    status, detail = manual_keys(home, "~/keys/client_id.bin", tmp_path / "private_key.pem")
    assert status == "FAIL" and "file not found" in detail
    assert "client-id starts with ~, which isn't expanded: use the full path" in detail


def test_key_files_name_a_dumped_file_beside_the_missing_one(home, tmp_path):
    (tmp_path / "device_client_id_blob").write_bytes(b"c")
    (tmp_path / "private_key").write_bytes(b"k")
    status, detail = manual_keys(home, tmp_path / "client_id.bin", tmp_path / "private_key.pem")
    assert status == "FAIL"
    assert "client-id: no file at that name, but device_client_id_blob is in that folder" in detail
    assert "private-key: no file at that name, but private_key is in that folder" in detail


def test_key_files_that_look_swapped_or_json(home, tmp_path):
    client, key = tmp_path / "client_id.bin", tmp_path / "private_key.pem"
    client.write_bytes(b"-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n")
    key.write_bytes(b"\x08\x01\x12\x10not a key")
    status, detail = manual_keys(home, client, key)
    assert status == "FAIL" and detail.startswith("the key files can't be loaded")
    assert "client-id looks like a private key: the two may be swapped" in detail
    assert "private-key looks like a client id: the two may be swapped" in detail
    client.write_text('{"client_id": "abc"}', encoding="utf-8")
    status, detail = manual_keys(home, client, key)
    assert "client-id looks like a JSON file, not a key file" in detail


def test_key_files_set_in_auth_json(home, tmp_path):
    write_config(home, {"cdm_options": {"key-mode-default": "manual"}})
    write_auth(home, **{"client-id": SECRET, "private_key": SECRET})
    status, detail = result(doctor.run(), "key files")
    assert status == "FAIL" and detail.startswith("client-id is not set; private-key is not set")
    assert "client-id and private-key are in auth.json: they belong in config.json" in detail
    assert SECRET not in detail


def test_key_mode_cdrm_warns_without_contacting_it(home, tmp_path, monkeypatch):
    from ofscraper.commands.scraper.actions.download.utils import keyhelpers

    monkeypatch.setattr(keyhelpers, "load_device", lambda *a: pytest.fail("loaded the keys"))
    write_config(home, {"cdm_options": {"key-mode-default": "cdrm"}})
    report = doctor.run()
    status, detail = result(report, "key files")
    assert status == "WARN" and "doesn't work" in detail and "key-mode-default to manual" in detail
    assert "then set client-id and private-key" in detail
    client, key = tmp_path / "client_id.bin", tmp_path / "private_key.pem"
    client.write_bytes(b"c")
    key.write_bytes(b"k")
    write_config(home, {"cdm_options": {"key-mode-default": "cdrm", "client-id": str(client), "private-key": str(key)}})
    status, detail = result(doctor.run(), "key files")
    assert status == "WARN" and "already set, so that switch is the whole fix" in detail


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


def test_key_mode_cdrm_with_a_server_of_your_own(home, monkeypatch):
    """OFSC_CDRM_URL set to a server other than the retired one: keys are
    asked from it, so the warning says that and not that cdrm can't work."""
    import ofscraper.utils.of_env.of_env as of_env

    url = f"http://user:{SECRET}@127.0.0.1:8080/api/decrypt"
    real = of_env.getattr
    monkeypatch.setattr(of_env, "getattr", lambda key, *a, **k: url if key == "CDRM" else real(key, *a, **k))
    write_config(home, {"cdm_options": {"key-mode-default": "cdrm"}})
    status, detail = result(doctor.run(), "key files")
    assert status == "WARN" and "doesn't work" not in detail
    assert "127.0.0.1" in detail and "cookies" in detail and SECRET not in detail


def test_key_files_that_name_a_folder(home, tmp_path):
    keys = tmp_path / "keys"
    keys.mkdir()
    (keys / "client_id.bin").write_bytes(b"c")
    (keys / "private_key.pem").write_bytes(b"k")
    status, detail = manual_keys(home, keys, keys / "private_key.pem")
    assert status == "FAIL"
    assert "client-id is a folder, not a file: client_id.bin is in it" in detail


def test_key_files_named_in_another_case(home, tmp_path):
    (tmp_path / "Client_ID.bin").write_bytes(b"c")
    (tmp_path / "DEVICE_PRIVATE_KEY").write_bytes(b"k")
    status, detail = manual_keys(home, tmp_path / "client_id.bin", tmp_path / "private_key.pem")
    assert status == "FAIL"
    if not (tmp_path / "client_id.bin").exists():
        # on a file system that ignores case (Windows, macOS) it is the file
        assert "client-id: no file at that name, but Client_ID.bin is in that folder" in detail
    assert "private-key: no file at that name, but DEVICE_PRIVATE_KEY is in that folder" in detail


def test_a_json_key_file_with_a_bom(home, tmp_path):
    client, key = tmp_path / "client_id.bin", tmp_path / "private_key.pem"
    client.write_bytes(b"\xef\xbb\xbf  {\"client_id\": \"abc\"}")
    key.write_bytes(b"not a key")
    status, detail = manual_keys(home, client, key)
    assert status == "FAIL" and "client-id looks like a JSON file, not a key file" in detail


def test_spaces_inside_a_token_are_named(home):
    write_config(home, {"main_profile": "main_profile"})
    write_auth(home, sess=SECRET[:10] + " " + SECRET[10:], auth_id="123 45")
    report = doctor.run()
    status, detail = result(report, "OnlyFans auth values")
    assert status == "WARN" and "sess has spaces" in detail and "auth_id has spaces" in detail
    assert SECRET[10:] not in json.dumps(report.results)


@pytest.mark.parametrize("value", [12345, True, ["x"]])
def test_an_auth_value_that_isnt_text_fails_and_isnt_cleaned(home, value):
    write_config(home, {"main_profile": "main_profile"})
    write_auth(home, auth_id=value)
    report = doctor.run()
    assert result(report, "OnlyFans auth")[0] == "FAIL"
    assert "not text" in result(report, "OnlyFans auth")[1]
    assert not [r for r in report.results if r["check"] == "OnlyFans auth values"]


# --- which Python a command on PATH starts ---

def pe_with_rcdata(resources, tail=b""):
    """A minimal PE32+ file with RT_RCDATA resources named as uv's
    trampolines name theirs (uv-trampoline-builder: UV_PYTHON_PATH, ...)."""
    import struct

    names, entries, blobs = b"", [], b""
    # the resource tree: root -> RT_RCDATA (id 10) -> one dir per name -> language 0 -> data
    count = len(resources)
    root = 16 + 8
    rcdata = root
    rcdata_size = 16 + 8 * count
    name_dirs = rcdata + rcdata_size
    data_entries = name_dirs + count * (16 + 8)
    name_strings = data_entries + count * 16
    strings = b""
    string_at = []
    for name, _ in resources:
        string_at.append(name_strings + len(strings))
        strings += struct.pack("<H", len(name)) + name.encode("utf-16-le")
    blobs_at = name_strings + len(strings)
    blobs_at += -blobs_at % 4
    section_va = 0x1000
    tree = struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 1) + struct.pack("<II", 10, 0x80000000 | rcdata)
    tree += struct.pack("<IIHHHH", 0, 0, 0, 0, count, 0)
    for i in range(count):
        tree += struct.pack("<II", 0x80000000 | string_at[i], 0x80000000 | (name_dirs + i * 24))
    data = b""
    for i, (_, value) in enumerate(resources):
        tree += struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 1) + struct.pack("<II", 0, data_entries + i * 16)
    for i, (_, value) in enumerate(resources):
        tree += struct.pack("<IIII", section_va + blobs_at + len(data), len(value), 0, 0)
        data += value + b"\0" * (-len(value) % 4)
    tree += strings
    tree += b"\0" * (blobs_at - len(tree)) + data
    raw_at = 0x400
    pe_at = 0x80
    opt = struct.pack("<H", 0x20B) + b"\0" * 106 + struct.pack("<I", 16)
    directories = [(0, 0)] * 16
    directories[2] = (section_va, len(tree))
    opt += b"".join(struct.pack("<II", *d) for d in directories)
    coff = struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, len(opt), 0x22)
    section = b".rsrc\0\0\0" + struct.pack("<IIIIIIHHI", len(tree), section_va, len(tree), raw_at, 0, 0, 0, 0, 0x40000040)
    head = b"MZ" + b"\0" * 58 + struct.pack("<I", pe_at)
    head += b"\0" * (pe_at - len(head)) + b"PE\0\0" + coff + opt + section
    return head + b"\0" * (raw_at - len(head)) + tree + tail


def test_a_uv_trampoline_names_its_python_in_a_resource(tmp_path):
    script = tmp_path / "ofscraper.exe"
    # absolute in this system's form: a Windows path on Windows
    python = str(tmp_path / "uv" / "tools" / "ofscraper" / "Scripts" / "python.exe")
    script.write_bytes(pe_with_rcdata([("UV_TRAMPOLINE_KIND", b"\x01"), ("UV_PYTHON_PATH", python.encode()),
                                       ("UV_SCRIPT_DATA", b"PK\x05\x06" + b"\0" * 18)]))
    assert doctor._script_python(str(script)) == python


def test_a_uv_trampolines_relative_python_is_beside_the_command(tmp_path, monkeypatch):
    folder = tmp_path / "Scripts"
    folder.mkdir()
    script = folder / "ofscraper.exe"
    script.write_bytes(pe_with_rcdata([("UV_TRAMPOLINE_KIND", b"\x01"), ("UV_PYTHON_PATH", b"python.exe")]))
    monkeypatch.chdir(tmp_path)
    assert doctor._script_python(str(script)) == str(folder / "python.exe")
    # the older form, with the path at the end of the file
    path = b"python.exe"
    script.write_bytes(b"MZ launcher" + path + len(path).to_bytes(4, "little") + b"UVPY")
    assert doctor._script_python(str(script)) == str(folder / "python.exe")


@pytest.mark.parametrize("line, python", [
    (b'#!"C:\\Program Files\\Python312\\Python.EXE"\r\n', "C:\\Program Files\\Python312\\Python.EXE"),
    (b"#!/opt/py/bin/python3.12 -s\n", "/opt/py/bin/python3.12"),
    (b"#!/opt/py/bin/PYTHON3 -E -s\n", "/opt/py/bin/PYTHON3"),
    (b"#!/bin/bash\n", None),
])
def test_shebang_forms(tmp_path, line, python):
    script = tmp_path / "ofscraper"
    script.write_bytes(line + b"import ofscraper\n")
    assert doctor._script_python(str(script)) == python


@pytest.mark.parametrize("second_line, python", [
    (b"'''exec' \"/opt/x y/bin/python3\" \"$0\" \"$@\"", "/opt/x y/bin/python3"),
    # shlex.quote'd, as some installers write it
    (b"'''exec' '/path with space/python' \"$0\" \"$@\"", "/path with space/python"),
    (b"'exec' '/path with space/python' \"$0\" \"$@\"", "/path with space/python"),
    (b"exec '/opt/x y/bin/python3' \"$0\" \"$@\"", "/opt/x y/bin/python3"),
    (b"exec '/opt/it'\"'\"'s/bin/python3' \"$0\" \"$@\"", "/opt/it's/bin/python3"),
])
def test_a_sh_wrapper_for_a_long_or_spaced_python_path(tmp_path, second_line, python):
    script = tmp_path / "ofscraper"
    script.write_bytes(b"#!/bin/sh\n" + second_line + b"\n' '''\nimport ofscraper\n")
    assert doctor._script_python(str(script)) == python


def test_a_truncated_or_damaged_windows_program_cant_tell(tmp_path):
    """Every offset in the PE and resource headers is checked against the
    file's length: a cut or damaged file names no Python, never raises."""
    import random

    whole = pe_with_rcdata([("UV_TRAMPOLINE_KIND", b"\x01"), ("UV_PYTHON_PATH", b"python.exe")])
    assert doctor._pe_resource(whole, "UV_PYTHON_PATH") == b"python.exe"
    for size in range(len(whole)):
        # only the padding after the value can go without losing it
        assert doctor._pe_resource(whole[:size], "UV_PYTHON_PATH") in (None, b"python.exe")
    rng = random.Random(0)
    for _ in range(2000):
        damaged = bytearray(whole)
        for _ in range(rng.randint(1, 4)):
            damaged[rng.randrange(len(damaged))] = rng.randrange(256)
        assert isinstance(doctor._pe_resource(bytes(damaged), "UV_PYTHON_PATH"), (bytes, type(None)))
    script = tmp_path / "ofscraper.exe"
    script.write_bytes(whole[:0x420])
    assert doctor._script_python(str(script)) is None


def test_a_pip_windows_launcher_with_an_upper_case_python(tmp_path):
    script = tmp_path / "ofscraper.exe"
    script.write_bytes(b"MZ launcher code" + b'#!"C:\\Python312\\PYTHON.EXE"\r\n' + b"PK\x03\x04zip")
    assert doctor._script_python(str(script)) == "C:\\Python312\\PYTHON.EXE"


def test_env_shebang_finds_the_python_on_path(home, tmp_path, monkeypatch):
    script = command_on_path(tmp_path, monkeypatch, f"#!/usr/bin/env -S {os.path.basename(sys.executable)} -s\nimport ofscraper\n".encode())
    monkeypatch.setenv("PATH", os.pathsep.join([str(script.parent), os.path.dirname(sys.executable)]))
    assert passes_as_this_install(script)


def test_a_shebang_through_a_linked_folder_is_this_install(home, tmp_path, monkeypatch):
    """macOS's /var is /private/var: the same folder by another path."""
    link = tmp_path / "linked"
    try:
        link.symlink_to(os.path.dirname(sys.executable), target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        # a symlink needs a privilege on Windows; a junction doesn't
        import _winapi

        _winapi.CreateJunction(os.path.dirname(sys.executable), str(link))
    python = link / os.path.basename(sys.executable)
    script = command_on_path(tmp_path, monkeypatch, f"#!{python}\nimport ofscraper\n".encode())
    assert result(doctor.run(), "ofscraper on PATH")[0] == "PASS"


def test_the_users_scripts_folder_of_the_preferred_scheme(home, tmp_path, monkeypatch):
    """A framework build on macOS installs --user commands under
    osx_framework_user, not posix_user."""
    import sysconfig

    script = command_on_path(tmp_path, monkeypatch, b"\x7fELF not a script")
    real = sysconfig.get_path
    monkeypatch.setattr(sysconfig, "get_preferred_scheme", lambda key: "osx_framework_user" if key == "user" else "posix_prefix")
    monkeypatch.setattr(sysconfig, "get_path", lambda name, scheme=None, *a, **k: str(script.parent) if scheme == "osx_framework_user" else real(name, *a, **k) if scheme is None else real(name, scheme, *a, **k))
    assert result(doctor.run(), "ofscraper on PATH")[0] == "PASS"


def test_key_mode_cdrm_with_a_malformed_server_address(home, monkeypatch):
    """An OFSC_CDRM_URL that urlsplit can't parse (an unclosed IPv6
    bracket) still gets the warning, without naming a host or crashing."""
    import ofscraper.utils.of_env.of_env as of_env

    url = f"http://user:{SECRET}@[::1/api/decrypt"
    real = of_env.getattr
    monkeypatch.setattr(of_env, "getattr", lambda key, *a, **k: url if key == "CDRM" else real(key, *a, **k))
    write_config(home, {"cdm_options": {"key-mode-default": "cdrm"}})
    status, detail = result(doctor.run(), "key files")
    assert status == "WARN" and "an unreadable address" in detail and "cookies" in detail
    assert SECRET not in detail and "::1" not in detail


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


@pytest.mark.parametrize("empty", ["", None, "  "])
def test_empty_key_placeholders_in_auth_json_arent_named(home, empty):
    write_config(home, {"cdm_options": {"key-mode-default": "manual"}})
    write_auth(home, **{"client-id": empty, "private_key": SECRET})
    status, detail = result(doctor.run(), "key files")
    assert status == "FAIL" and "private-key is in auth.json: it belongs in config.json" in detail
    assert "client-id and" not in detail
