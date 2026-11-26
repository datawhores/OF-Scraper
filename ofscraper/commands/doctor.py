"""Check the setup without running a scrape: which install is running,
config, logins on file, ffmpeg, key files, folders, free space and the
database setting.

It reads config.json as it is, changes nothing, makes no connection and
never asks a question. Each line is PASS, WARN, FAIL or SKIP; the exit status
is 1 when anything fails. No login value, password or key is printed.

--online also connects: to PostgreSQL, to the site to check the login (with
the scraper's own session), to the signing rule sources and to Stash. It
isn't read-only: it starts the scraper as a run does, which may rewrite
config.json and create folders, and the signing rule and Fansly's device id
are kept as a run keeps them. It is skipped where the offline checks found
something that would make the start ask a question.
"""

import argparse
import contextlib
import getpass
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import sysconfig
import urllib.parse

import ofscraper.utils.of_env.of_env as of_env

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
OF_AUTH_KEYS = ["sess", "auth_id", "user_agent", "x-bc"]


def _homes():
    """The home folder as it may be written in a path: as given and with
    links followed, each also with forward slashes; longest first."""
    home = pathlib.Path.home()
    found = {str(home)}
    with contextlib.suppress(OSError, RuntimeError):
        found.add(str(home.resolve()))
    found |= {h.replace("\\", "/") for h in found}
    return sorted((h.rstrip("\\/") for h in found if len(h.rstrip("\\/")) > 1), key=len, reverse=True)


def redact(text):
    """text with the home folder written as ~ and the login name, where it
    is a folder name elsewhere, as <user>: the output is meant for public
    issues."""
    flags = re.IGNORECASE if os.name == "nt" else 0
    for home in _homes():
        text = re.sub(re.escape(home) + r"(?=$|[\\/])", "~", text, flags=flags)
    try:
        user = getpass.getuser()
    except Exception:
        user = None
    if user:
        text = re.sub(r"(?<=[\\/])" + re.escape(user) + r"(?=$|[\\/])", "<user>", text, flags=flags)
    return text


class Report:
    def __init__(self):
        self.results = []

    def add(self, status, check, detail=""):
        self.results.append({"status": status, "check": check, "detail": redact(str(detail))})

    @property
    def failed(self):
        return any(r["status"] == FAIL for r in self.results)

    def text(self):
        width = max(len(r["check"]) for r in self.results)
        return "\n".join(
            f"{r['status']:<5} {r['check']:<{width}}  {r['detail']}".rstrip()
            for r in self.results
        )


def config_path(given=None):
    """Where config.json is, by get_config_path's rule (utils/paths/common.py),
    without reading settings or creating anything."""
    home = pathlib.Path.home() / of_env.getattr("configPath")
    name = of_env.getattr("configFile")
    if not given:
        return home / name
    path = pathlib.Path(given)
    if path.is_file():
        return path
    if path.is_dir() or path.suffix == "":
        return path / name
    if str(path.parent) == ".":
        return home / path
    return path


def read_config(path, report):
    """The settings in config.json, or None for the built-in defaults."""
    import ofscraper.utils.config.file as config_file
    import ofscraper.utils.encoding as encoding

    if not path.exists():
        report.add(WARN, "config file", f"{path} isn't there: a run makes one with the defaults")
        return None
    try:
        text = encoding.read_text_file(path)
    except (OSError, UnicodeDecodeError) as error:
        report.add(FAIL, "config file", f"{path} can't be read: {error}")
        return None
    try:
        # the run's own check (config_context), which doesn't repair
        # unescaped backslashes the way json_loads does
        config = config_file.checked(text)
    except json.JSONDecodeError as error:
        report.add(FAIL, "config file",
                   f"{path} isn't valid JSON: {error.msg} at line {error.lineno}, column {error.colno}."
                   " The rest is checked with the defaults")
        return None
    except config_file.NotAnObjectError as error:
        report.add(FAIL, "config file", f"{path}: {error}. The rest is checked with the defaults")
        return None
    report.add(PASS, "config file", str(path))
    return config


def _config(config):
    """What a config getter is given: the settings, or False for the
    defaults. An empty {} is the defaults too: the getters would open
    config.json through the settings for it."""
    return config or False


def _get(getter, config):
    """A config getter's value for this config, or the default."""
    return getter(config=_config(config))


def profile_folder(config, profile, path):
    import ofscraper.utils.config.data as data
    import ofscraper.utils.profiles.tools as profile_tools

    name = profile or _get(data.get_main_profile, config)
    return path.parent / profile_tools.profile_name_fixer(name)


CONFIG_AUTH_KEYS = ["sess", "auth_id", "x-bc", "x_bc"]


def _auth_value_findings(auth):
    """What's wrong with each auth value after a run's own clean-up; the
    fields are named, their values never shown."""
    import ofscraper.utils.auth.data as auth_data

    findings = []
    for key in OF_AUTH_KEYS:
        value = auth.get(key)
        if not isinstance(value, str):
            continue
        value = auth_data.fix_val(value)
        if key == "sess" and value.lower() == "deleted":
            findings.append('sess is "deleted": the browser session had logged out, so log in and copy it again')
            continue
        found = []
        if any(c in value for c in "\"'"):
            found.append("quotes")
        # a user agent has ;, = and spaces of its own
        if key != "user_agent":
            if " " in value:
                found.append("spaces")
            found += [c for c in ";=" if c in value]
        if any(not (" " <= c <= "~") for c in value):
            found.append("characters outside printable ASCII")
        if found:
            findings.append(f"{key} has {', '.join(found)}")
    return findings


def check_config_auth(config, report):
    """Auth values put in config.json, which a run never reads from there."""
    if not isinstance(config, dict):
        return
    sections = [config] + [v for v in config.values() if isinstance(v, dict)]
    found = [k for k in CONFIG_AUTH_KEYS if any(section.get(k) not in (None, "") for section in sections)]
    if found:
        report.add(WARN, "auth in config", f"config.json has {', '.join(found)}: these belong in auth.json, and a run doesn't read them from config.json")


def check_onlyfans_auth(folder, report):
    import ofscraper.utils.auth.utils.dict as auth_dict
    import ofscraper.utils.encoding as encoding

    path = folder / of_env.getattr("authFile")
    if not path.exists():
        # a run asks for the login and writes the file
        report.add(WARN, "OnlyFans auth", f"{path} isn't there: a run asks for the login and makes it")
        return
    try:
        text = encoding.read_text_file(path)
        # get_auth_dict reads the profile's file through the settings for ""
        if not text.strip():
            report.add(FAIL, "OnlyFans auth", f"{path} is empty")
            return
        auth = auth_dict.get_auth_dict(text)
    except (OSError, ValueError, AttributeError, TypeError) as error:
        # TypeError: JSON null, a number or true/false, which get_auth_dict can't look in
        report.add(FAIL, "OnlyFans auth", f"{path} can't be read: {type(error).__name__}")
        return
    if not isinstance(auth, dict):
        report.add(FAIL, "OnlyFans auth", f"{path} doesn't hold the auth fields")
        return
    # a run strips each value (auth/data.py fix_val), which fails on a
    # number or true/false, and asks for one that is only spaces
    not_text = [k for k in OF_AUTH_KEYS if auth.get(k) is not None and not isinstance(auth.get(k), str)]
    blank = [k for k in OF_AUTH_KEYS if k not in not_text and not (auth.get(k) or "").strip()]
    if not_text:
        report.add(FAIL, "OnlyFans auth", f"not text in {path} (put the value in quotes): {', '.join(not_text)}")
    elif blank:
        report.add(FAIL, "OnlyFans auth", f"blank in {path}: {', '.join(blank)}")
    else:
        report.add(PASS, "OnlyFans auth", f"{path} (every field set; the login itself is checked with --online)")
    findings = _auth_value_findings(auth)
    if findings:
        report.add(WARN, "OnlyFans auth values", f"a run would send these as they are, and the site may reject them: {'; '.join(findings)}")


def check_fansly_auth(folder, report):
    import ofscraper.sites.fansly.auth as fansly_auth
    import ofscraper.sites.fansly.constants as fansly_constants

    path = folder / fansly_constants.AUTH_FILE
    if not path.exists():
        report.add(WARN, "Fansly auth", f"{path} isn't there: a run asks for the login and makes it")
        return
    try:
        auth = fansly_auth.read_auth(path)
    except (OSError, ValueError, AttributeError) as error:
        report.add(FAIL, "Fansly auth", f"{path} can't be read: {type(error).__name__}")
        return
    problems = fansly_auth.problems(auth)
    if problems:
        report.add(FAIL, "Fansly auth", f"{path}: {'; '.join(problems)}")
    else:
        report.add(PASS, "Fansly auth", f"{path} (the login itself is checked with --online)")


def check_auth(config, folder, site, report):
    import ofscraper.sites as sites

    for name, check in ((sites.ONLYFANS, check_onlyfans_auth), (sites.FANSLY, check_fansly_auth)):
        label = "OnlyFans auth" if name == sites.ONLYFANS else "Fansly auth"
        if name == site:
            check(folder, report)
            if name == sites.ONLYFANS:
                check_config_auth(config, report)
        else:
            report.add(SKIP, label, f"not used: the profile is for {sites.SITE_NAMES[site]}")


def _norm(path):
    return os.path.normcase(os.path.abspath(path))


def _pe_resource(data, name):
    """An RT_RCDATA resource of a Windows program, by name, or None: where
    uv's trampolines keep the Python they start (UV_PYTHON_PATH)."""

    def word(at, size):
        if at < 0 or at + size > len(data):
            raise ValueError("outside the file")
        return int.from_bytes(data[at:at + size], "little")

    try:
        if data[:2] != b"MZ":
            return None
        pe = word(0x3C, 4)
        if data[pe:pe + 4] != b"PE\0\0":
            return None
        sections, optional_size = word(pe + 6, 2), word(pe + 20, 2)
        optional = pe + 24
        # the data directories follow the optional header's fields: 96
        # bytes of them in PE32, 112 in PE32+; the resources are the third
        directories = optional + (96 if word(optional, 2) == 0x10B else 112)
        table = [
            (word(at + 12, 4), max(word(at + 8, 4), word(at + 16, 4)), word(at + 20, 4))
            for at in range(optional + optional_size, optional + optional_size + 40 * sections, 40)
        ]

        def offset(rva):
            for address, size, raw in table:
                if address <= rva < address + size:
                    return rva - address + raw
            raise ValueError("not in a section")

        base = offset(word(directories + 16, 4))

        def entries(directory):
            count = word(directory + 12, 2) + word(directory + 14, 2)
            for at in range(directory + 16, directory + 16 + 8 * min(count, 4096), 8):
                yield word(at, 4), word(at + 4, 4)

        def below(pointer):
            return base + (pointer & 0x7FFFFFFF)

        def named(key):
            if not key & 0x80000000:
                return None
            at = below(key)
            return data[at + 2:at + 2 + 2 * word(at, 2)].decode("utf-16-le", "replace")

        # the tree: type (RT_RCDATA is 10), then name, then language
        rcdata = next((below(p) for key, p in entries(base) if key == 10 and p & 0x80000000), None)
        if rcdata is None:
            return None
        found = next((below(p) for key, p in entries(rcdata) if (named(key) or "").upper() == name and p & 0x80000000), None)
        if found is None:
            return None
        languages = [p for _key, p in entries(found)]
        if not languages or languages[0] & 0x80000000:
            return None
        entry = below(languages[0])
        start, size = offset(word(entry, 4)), word(entry + 4, 4)
        if start + size > len(data):
            return None
        return data[start:start + size]
    except ValueError:
        return None


PYTHON_NAME = re.compile(r"pythonw?[\d.]*(?:\.exe)?", re.IGNORECASE)


def _shebang_python(line):
    """The Python a #! line starts, or None: its program (quoted or not; the
    flags after it aren't part of it) when that is a python, or the python
    /usr/bin/env would find on PATH."""
    words = [quoted or bare for quoted, bare in re.findall(r'"([^"]*)"|(\S+)', line)]
    if words and re.split(r"[\\/]", words[0])[-1].lower() in ("env", "env.exe"):
        words = [w for w in words[1:] if not w.startswith("-") and "=" not in w][:1]
        if words and PYTHON_NAME.fullmatch(words[0]):
            return shutil.which(words[0]) or words[0]
        return None
    if words and PYTHON_NAME.fullmatch(re.split(r"[\\/]", words[0])[-1]):
        return words[0]
    return None


def _exec_target(data):
    """The program a shell script hands over to with exec, or None."""
    for raw in data.splitlines()[1:100]:
        try:
            words = shlex.split(raw.decode("utf-8", "replace"), comments=True)
        except ValueError:
            continue
        if len(words) > 1 and words[0] == "exec":
            return words[1]
    return None


def _is_script(path):
    try:
        with open(path, "rb") as file:
            return file.read(2) == b"#!"
    except OSError:
        return False


def _follow(script, depth=0):
    """(the Python an ofscraper command on PATH starts or None, the last
    file read): from its shebang (or the one in a Windows launcher, or uv's
    trampoline), following a shell wrapper that execs a python or another
    command."""
    try:
        with open(script, "rb") as file:
            data = file.read(4 * 2**20)
    except OSError:
        return None, script
    python = _script_python(script, data)
    if python or not data.startswith(b"#!") or depth >= 4:
        return python, script
    target = _exec_target(data)
    if not target:
        return None, script
    if PYTHON_NAME.fullmatch(re.split(r"[\\/]", target)[-1]):
        return target, script
    found = target if os.path.isabs(target) else shutil.which(target)
    if not found or not os.path.isfile(found):
        return None, script
    return _follow(found, depth + 1)


def _script_python(script, data=None):
    """The Python an ofscraper command on PATH starts, from its shebang (or
    the one in a Windows launcher, or uv's trampoline), or None."""
    if data is None:
        try:
            with open(script, "rb") as file:
                data = file.read(4 * 2**20)
        except OSError:
            return None
    uv = _pe_resource(data, "UV_PYTHON_PATH")
    if uv is None and data[-4:] in (b"UVSC", b"UVPY") and len(data) > 8:
        # uv's trampolines before the path moved into a resource
        size = int.from_bytes(data[-8:-4], "little")
        if 0 < size < len(data) - 8:
            uv = data[-8 - size:-8]
    if uv:
        # a relative path is beside the trampoline, as uv-trampoline reads it
        return os.path.join(os.path.dirname(os.path.abspath(script)), uv.decode("utf-8", "replace"))
    # pip's wrapper for long paths: #!/bin/sh, then '''exec' "/path/python" "$0" "$@";
    # the path can also be in single quotes, as shlex.quote writes it
    wrapped = re.match(rb"#!/bin/sh\r?\n([^\r\n]*)", data)
    if wrapped:
        try:
            words = shlex.split(wrapped.group(1).decode("utf-8", "replace"))
        except ValueError:
            words = []
        # only a python: a wrapper that execs another command is followed
        # by _follow
        if len(words) > 1 and words[0] == "exec" and PYTHON_NAME.fullmatch(re.split(r"[\\/]", words[1])[-1]):
            return words[1]
    # a script's first line, or the last #! line of a Windows launcher
    # (distlib's: the launcher, then the #! line, then a zip of the script)
    if data.startswith(b"#!"):
        line = data.split(b"\n", 1)[0]
    else:
        found = re.findall(rb"#!([^\r\n]*)\r?\n", data)
        line = found[-1] if found else None
    if line is None:
        return None
    return _shebang_python(line.removeprefix(b"#!").decode("utf-8", "replace").strip())


def _scripts_dirs():
    """Where this Python's installs put their commands."""
    dirs = {os.path.dirname(sys.executable), sysconfig.get_path("scripts")}
    try:
        # posix_user, nt_user, or osx_framework_user for a macOS framework build
        dirs.add(sysconfig.get_path("scripts", sysconfig.get_preferred_scheme("user")))
    except KeyError:
        pass
    return {_norm(os.path.realpath(d)) for d in dirs if d}


def check_install(report):
    """Which install is running, and whether ofscraper on PATH is another."""
    from ofscraper.__version__ import __dist_name__, __version__

    frozen = getattr(sys, "frozen", False)
    if frozen:
        report.add(PASS, "install", f"{__dist_name__} {__version__}, binary {sys.executable}")
    else:
        package = pathlib.Path(__file__).resolve().parents[1]
        report.add(PASS, "install", f"{__dist_name__} {__version__}, Python {sys.executable}, package {package}")
    script = shutil.which("ofscraper")
    if not script:
        report.add(SKIP, "ofscraper on PATH", "no ofscraper command on PATH")
        return
    python, final = _follow(script)
    if frozen:
        same = _norm(os.path.realpath(final)) == _norm(os.path.realpath(sys.executable))
    else:
        if python:
            # python and python3 in one folder can be the same install;
            # two virtual environments' pythons can be links to one file
            same = _norm(python) == _norm(sys.executable) or (
                _norm(os.path.realpath(os.path.dirname(python))) == _norm(os.path.realpath(os.path.dirname(sys.executable)))
                and _norm(os.path.realpath(python)) == _norm(os.path.realpath(sys.executable))
            )
        else:
            same = _norm(os.path.dirname(os.path.realpath(final))) in _scripts_dirs()
    if not same and not python and _is_script(final):
        # a wrapper or shim whose program is only known when it runs
        report.add(SKIP, "ofscraper on PATH",
                   f"{script} is a script that doesn't name the Python or ofscraper it runs: doctor can't tell"
                   " whether it runs this install")
        return
    if same:
        report.add(PASS, "ofscraper on PATH", f"{script}, this install")
    else:
        report.add(WARN, "ofscraper on PATH",
                   f"{script} is a different install from the one running doctor ({sys.executable}):"
                   " the ofscraper command doesn't run this one")


def check_ffmpeg(config, report):
    import ofscraper.utils.config.data as data
    import ofscraper.utils.system.ffmpeg as ffmpeg

    configured = _get(data.get_ffmpeg, config) or of_env.getattr("FFMPEG_DEFAULT")
    if configured:
        try:
            is_ffmpeg, version, major = ffmpeg.ffmpeg_version(configured) if shutil.which(configured) else (None, None, None)
        except (OSError, subprocess.SubprocessError):
            is_ffmpeg, version, major = None, None, None
        if is_ffmpeg and major is not None and major < 6:
            report.add(FAIL, "ffmpeg", f"{configured} is version {version}; protected videos need 6 or newer")
            return None
        if not is_ffmpeg:
            report.add(FAIL, "ffmpeg", f"the configured ffmpeg {configured} isn't there or isn't ffmpeg")
            return None
    path, source, version = ffmpeg.find_ffmpeg(configured)
    if not path:
        report.add(FAIL, "ffmpeg", "no ffmpeg 6 or newer found in the config, pyffmpeg or PATH")
        return None
    report.add(PASS, "ffmpeg", f"{version or 'version unknown'} (from {source}): {path}")
    return path


def check_ffprobe(ffmpeg_path, report):
    if not ffmpeg_path:
        report.add(SKIP, "ffprobe", "no ffmpeg to look beside")
        return
    name = "ffprobe.exe" if ffmpeg_path.lower().endswith(".exe") else "ffprobe"
    beside = os.path.join(os.path.dirname(ffmpeg_path), name)
    found = beside if os.path.exists(beside) else shutil.which("ffprobe")
    if found:
        report.add(PASS, "ffprobe", found)
    else:
        report.add(WARN, "ffprobe", "not found beside ffmpeg or in PATH: media lengths come from ffmpeg instead")


KEY_FILE_NAMES = {
    "client-id": ["device_client_id_blob", "client_id.bin", "client_id"],
    "private-key": ["device_private_key", "private_key.pem", "private_key"],
}


def _key_file_hint(name, value):
    """Why a key file named in the config isn't there, when it can tell."""
    value = str(value or "").strip()
    if not value or pathlib.Path(value).is_file():
        return None
    if value.startswith("~"):
        return f"{name} starts with ~, which isn't expanded: use the full path"
    path = pathlib.Path(value)
    if path.is_dir():
        try:
            inside = sorted(f.name for f in path.iterdir() if f.is_file() and f.name.lower() in KEY_FILE_NAMES[name])
        except OSError:
            inside = []
        found = f": {', '.join(inside)} {'is' if len(inside) == 1 else 'are'} in it" if inside else ""
        return f"{name} is a folder, not a file{found}"
    # in any case: on Linux and in Docker, Client_ID.bin isn't client_id.bin
    stem, whole = path.stem.lower(), path.name.lower()
    try:
        beside = sorted(
            f.name for f in path.parent.iterdir()
            if f.is_file() and f.name != path.name
            and (f.name.lower() in KEY_FILE_NAMES[name] or stem in (f.stem.lower(), f.name.lower()) or f.stem.lower() == whole)
        )
    except OSError:
        return None
    if beside:
        return f"{name}: no file at that name, but {', '.join(beside)} {'is' if len(beside) == 1 else 'are'} in that folder"
    return None


def _key_content_hint(name, value):
    """What a key file that can't be loaded looks like instead, if it's clear."""
    try:
        with open(str(value).strip(), "rb") as file:
            start = file.read(64)
    except OSError:
        return None
    # a JSON file saved by Notepad starts with a byte order mark
    start = start.removeprefix(b"\xef\xbb\xbf").lstrip()
    if start.startswith(b"{"):
        return f"{name} looks like a JSON file, not a key file"
    if name == "client-id" and start.startswith(b"-----BEGIN"):
        return "client-id looks like a private key: the two may be swapped"
    if name == "private-key" and start[:1] == b"\x08":
        return "private-key looks like a client id: the two may be swapped"
    return None


def _keys_in_auth_file(folder):
    """The key settings put in auth.json instead of config.json; names only."""
    import ofscraper.utils.encoding as encoding

    if folder is None:
        return []
    try:
        auth = json.loads(encoding.read_text_file(folder / of_env.getattr("authFile")))
    except (OSError, ValueError):
        return []
    if not isinstance(auth, dict):
        return []
    inner = auth.get("auth") if isinstance(auth.get("auth"), dict) else {}
    # an empty "" or null is a placeholder, not a key put in the wrong file
    keys = {k for part in (auth, inner) for k, v in part.items() if v is not None and str(v).strip()}
    return [name for name in KEY_FILE_NAMES if name in keys or name.replace("-", "_") in keys]


def _with_hints(problem, hints):
    hints = [h for h in hints if h]
    return f"{problem} ({'; '.join(hints)})" if hints else problem


def check_keys(config, site, report, folder=None):
    import ofscraper.sites as sites
    import ofscraper.utils.config.data as data
    from ofscraper.commands.scraper.actions.download.utils import keyhelpers

    if site == sites.FANSLY:
        # as at a run's start (system/network.py): Fansly video has no DRM
        report.add(SKIP, "key files", "not used: Fansly videos aren't protected")
        return
    mode = _get(data.get_key_mode, config)
    client_id = _get(data.get_client_id, config) if config else None
    private_key = _get(data.get_private_key, config) if config else None
    if mode == "cdrm":
        if keyhelpers.cdm_key_problems("manual", client_id, private_key):
            fix = "then set client-id and private-key to your key files"
        else:
            fix = "client-id and private-key are already set, so that switch is the whole fix"
        url = str(of_env.getattr("CDRM") or "").strip()
        try:
            retired = keyhelpers.cdrm_retired(url)
            host = urllib.parse.urlsplit(url).hostname
        except ValueError:  # a malformed address, e.g. an unclosed IPv6 bracket
            retired, host = False, None
        if url and not retired:
            # a server of the user's own (#677): only its host is shown, as
            # the address can hold a login
            host = host or "an unreadable address"
            report.add(WARN, "key files",
                       f"key mode cdrm: keys are asked from the server in OFSC_CDRM_URL ({host}), which is sent"
                       " your OnlyFans cookies, so use only a server you run (not contacted by this check)."
                       f" The cdrm mode is deprecated: to stop using it, set key-mode-default to manual; {fix}")
            return
        report.add(WARN, "key files",
                   "key mode cdrm: the cdrm service doesn't work, so protected videos will fail"
                   f" (not contacted by this check). Set key-mode-default to manual; {fix}")
        return
    if mode != "manual":
        report.add(PASS, "key files", f"key mode {mode}: no key files needed")
        return
    if not str(client_id or "").strip() and not str(private_key or "").strip() and not _keys_in_auth_file(folder):
        # the default on a fresh install: a run goes on without them (keys
        # put in auth.json instead are a setup gone wrong, a FAIL below)
        report.add(WARN, "key files", "no key files set up yet: protected (DRM) videos are skipped until client-id and private-key are set")
        return
    problem = keyhelpers.cdm_key_problems(mode, client_id, private_key)
    if problem:
        hints = [_key_file_hint("client-id", client_id), _key_file_hint("private-key", private_key)]
        misplaced = _keys_in_auth_file(folder)
        if misplaced:
            hints.append(f"{' and '.join(misplaced)} " + ("is in auth.json: it belongs" if len(misplaced) == 1 else "are in auth.json: they belong") + " in config.json")
        report.add(FAIL, "key files", _with_hints(problem, hints))
        return
    try:
        keyhelpers.load_device(private_key, client_id)
    except Exception as error:
        hints = [_key_content_hint("client-id", client_id), _key_content_hint("private-key", private_key)]
        report.add(FAIL, "key files", _with_hints(f"the key files can't be loaded: {type(error).__name__}", hints))
        return
    report.add(PASS, "key files", f"client-id {client_id}, private-key {private_key}")


def _free(path):
    try:
        gib = shutil.disk_usage(path).free / 2**30
    except OSError as error:
        return f"free space can't be read: {error.strerror or type(error).__name__}"
    return f"{gib:.1f} GiB free"


def _device(path):
    try:
        return os.stat(path).st_dev
    except OSError:
        return None


def _check_path(save):
    """The folder the free-space limit is measured at: OFSC_DISK_SPACE_CHECK_PATH,
    or when that is empty the disk that holds the save folder, measured at
    its nearest folder that is there, a link followed first
    (free.get_check_path's rule)."""
    measured = of_env.getattr("DISK_SPACE_CHECK_PATH")
    if measured:
        return measured
    path = save.resolve()
    while not path.exists() and path.parent != path:
        path = path.parent
    return path


# where Linux and macOS mount drives and shares; a missing save folder whose
# nearest folder that is there is one of these is on a drive not mounted
MOUNT_PARENTS = ("/", "/mnt", "/media", "/Volumes", "/net")
# this holds a folder per user, which holds the mounts (/run/media/<user>)
USER_MOUNT_PARENTS = ("/run/media",)


def _windows():
    return os.name == "nt"


def _unmounted(save):
    """The save folder isn't there and nothing is above it up to a place
    drives are mounted: its drive or share likely isn't mounted."""
    here = save.absolute()
    while not here.exists() and here.parent != here:
        here = here.parent
    return here in {pathlib.Path(p) for p in MOUNT_PARENTS} or here.parent in {
        pathlib.Path(p) for p in USER_MOUNT_PARENTS
    }


def check_folders(config, report):
    import ofscraper.utils.config.data as data
    import ofscraper.utils.paths.common as common_paths

    save = pathlib.Path(os.path.expanduser(common_paths.get_save_location(_config(config))))
    if save.is_dir():
        report.add(PASS, "save folder", f"{save}, {_free(save)}")
    elif not _windows() and _unmounted(save):
        report.add(FAIL, "save folder", f"{save} isn't there: is the drive or share mounted?")
    elif pathlib.Path(save.anchor or ".").is_dir():
        # the download makes it, parents included
        report.add(WARN, "save folder", f"{save} isn't there yet: a run makes it")
    else:
        report.add(FAIL, "save folder", f"{save} isn't there, nor is its drive {save.anchor}")
    temp = _get(data.get_TempDir, config)
    if temp:
        temp = pathlib.Path(os.path.expanduser(temp))
        if temp.is_dir():
            report.add(PASS, "temp folder", f"{temp}, {_free(temp)}")
        else:
            report.add(FAIL, "temp folder", f"{temp} isn't there")
    else:
        report.add(PASS, "temp folder", "not set: files are written beside their final place")

    limit = _get(data.get_system_freesize, config) or 0
    if not limit:
        report.add(PASS, "free-space limit", "off")
        return
    measured = _check_path(save)
    if _device(measured) is None:
        report.add(FAIL, "free-space limit", f"measures {measured}, which isn't there (set OFSC_DISK_SPACE_CHECK_PATH)")
    elif save.is_dir() and _device(measured) != _device(save):
        report.add(WARN, "free-space limit",
                   f"measures {measured}, but downloads go to another disk ({save}); set OFSC_DISK_SPACE_CHECK_PATH")
    else:
        report.add(PASS, "free-space limit", f"{limit} bytes, measured at {measured}, {_free(measured)}")


def check_database(report):
    import ofscraper.db.postgres as postgres

    url = postgres.url()
    if not url:
        report.add(PASS, "database", "SQLite, one user_data.db per creator")
        return
    where = postgres.describe(url)
    try:
        import psycopg  # noqa: F401
        import psycopg_pool  # noqa: F401
    except ImportError:
        report.add(FAIL, "database", f"PostgreSQL at {where} is set, but its driver isn't installed")
        return
    report.add(PASS, "database", f"PostgreSQL at {where}; the connection is checked with --online")


def _status(report, check):
    found = [r for r in report.results if r["check"] == check]
    return found[0]["status"] if found else None


def check_postgres(report, site):
    import ofscraper.db.postgres as postgres

    if not postgres.url():
        return
    if _status(report, "database") == FAIL:
        report.add(SKIP, "PostgreSQL", "the database setting failed above")
        return
    try:
        # the site is given: the settings would parse doctor's own
        # command line, as the start hasn't set it yet
        version = postgres.POSTGRES.check(site)
    except Exception as error:
        report.add(FAIL, "PostgreSQL", str(error))
        return
    report.add(PASS, "PostgreSQL", f"{postgres.describe()}, server version {version}")


def start(config, profile, site):
    """The normal start up to where a run would begin, without running one."""
    import ofscraper.main.open.load as load
    import ofscraper.managers.manager as manager

    argv = ["ofscraper"]
    for flag, value in (("--config", config), ("--profile", profile), ("--site", site)):
        if value:
            argv += [flag, value]
    sys.argv = argv
    load.settings_loader()
    load.setdate()
    load.readConfig()
    load.setLogger()
    load.make_folder()
    if not isinstance(manager.Manager, manager.mainManager):
        manager.Manager = manager.mainManager()


def check_login(report, site_name):
    import ofscraper.data.api.init as init

    status, message = init.auth_status()
    if status == "UP":
        report.add(PASS, f"{site_name} login", "logged in")
    elif status == "DOWN":
        report.add(FAIL, f"{site_name} login", "the site rejected the login: update the auth file")
    else:
        report.add(WARN, f"{site_name} login", f"couldn't be checked: {message}")


def check_signing_rules(report):
    import ofscraper.utils.auth.request as request

    used, failed = request.last_attempt["used"], request.last_attempt["failed"]
    detail = "; ".join(f"{source}: {reason}" for source, reason in failed)
    if used and not failed:
        report.add(PASS, "signing rules", f"from {used}")
    elif used:
        report.add(WARN, "signing rules", f"from {used}, after others gave none ({detail})")
    elif failed:
        report.add(FAIL, "signing rules", f"no source gave a rule ({detail})")
    else:
        report.add(SKIP, "signing rules", "not fetched")


def check_stash(report):
    from ofscraper.commands.stash_sync import API_KEY_ENV, URL_ENV, StashClient, StashError

    url = os.environ.get(URL_ENV, "").strip()
    if not url:
        return
    try:
        data = StashClient(url, os.environ.get(API_KEY_ENV), timeout=15).call(
            "query { version { version } }", retries=0
        )
        version = ((data or {}).get("version") or {}).get("version") or "version unknown"
    except (StashError, OSError, ValueError) as error:
        report.add(FAIL, "Stash", str(error))
        return
    except (KeyError, AttributeError, TypeError) as error:
        # JSON that isn't a GraphQL reply: not Stash, or a proxy's page
        report.add(FAIL, "Stash", f"{url}: unexpected reply ({type(error).__name__})")
        return
    report.add(PASS, "Stash", f"{url}, {version}")


def run_online(report, config=None, profile=None, site=None):
    """--online: the checks that connect, each skipped with its reason when
    an offline check found what it needs broken."""
    import ofscraper.sites as sites

    check_postgres(report, site)
    site_name = sites.SITE_NAMES[site]
    auth_check = "OnlyFans auth" if site == sites.ONLYFANS else "Fansly auth"
    login = f"{site_name} login"
    if _status(report, "config file") == FAIL:
        report.add(SKIP, login, "the config file failed above: a run would stop to ask about it")
    elif _status(report, auth_check) == FAIL:
        report.add(SKIP, login, "the auth file failed above: a run would stop to ask for it")
    elif _status(report, auth_check) == WARN:
        report.add(SKIP, login, "there's no auth file yet: a run would stop to ask for the login")
    else:
        try:
            start(config, profile, site)
            check_login(report, site_name)
        except (Exception, SystemExit) as error:
            report.add(FAIL, login, f"the start failed: {error}")
        if site == sites.ONLYFANS:
            check_signing_rules(report)
    check_stash(report)


def run(config=None, profile=None, site=None, online=False):
    """Every offline check, and with online the ones that connect; the Report."""
    import ofscraper.sites as sites

    report = Report()
    check_install(report)
    path = config_path(config)
    settings = read_config(path, report)
    folder = profile_folder(settings, profile, path)
    site = sites.normalize(site) or sites.read_profile_site(folder)
    report.add(PASS, "profile", f"{folder.name} ({sites.SITE_NAMES[site]})" + ("" if folder.is_dir() else ", folder isn't there yet"))
    check_auth(settings, folder, site, report)
    ffmpeg_path = check_ffmpeg(settings, report)
    check_ffprobe(ffmpeg_path, report)
    check_keys(settings, site, report, folder)
    check_folders(settings, report)
    check_database(report)
    if online:
        run_online(report, config, profile, site)
    else:
        report.add(SKIP, "login", "run with --online to check the login, PostgreSQL and Stash")
    return report


def main(argv=None):
    import ofscraper.sites as sites

    parser = argparse.ArgumentParser(prog="ofscraper doctor", description=__doc__)
    parser.add_argument("--config", metavar="PATH", help="The config file or folder, as for a run's --config")
    parser.add_argument("--profile", metavar="NAME", help="The profile to check (default: the config's main profile)")
    parser.add_argument("--site", choices=list(sites.SITES), help="Check this site's auth file, not the profile's site")
    parser.add_argument("--json", action="store_true", help="Print the results as JSON")
    parser.add_argument("--online", action="store_true", help="Also connect: PostgreSQL, the login, the signing rules and Stash. Not read-only: it starts the scraper as a run does")
    args = parser.parse_args(argv)
    # with --json, what the start prints (a config made, log lines) goes to
    # stderr, so stdout is only the JSON
    quiet = contextlib.redirect_stdout(sys.stderr) if args.json else contextlib.nullcontext()
    try:
        with quiet:
            report = run(args.config, args.profile, args.site, online=args.online)
    except KeyboardInterrupt:
        parser.exit(130, "Stopped\n")
    if args.json:
        print(json.dumps({"ok": not report.failed, "results": report.results}, indent=2))
    else:
        print(report.text())
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
