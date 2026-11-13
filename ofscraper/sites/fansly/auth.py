"""Fansly credentials, kept in ``fansly_auth.json`` in the profile folder.

Fields:
- ``authorization_token``: the token the web app stores in localStorage under
  ``session_active_session`` (its ``token`` key), or the ``authorization``
  request header. Without a "Bearer" prefix.
- ``user_agent``: the user agent of the browser the token came from.
- ``check_key`` (optional): the web app's current check key, used for the
  ``fansly-client-check`` header. A built-in default is used when empty.
- ``device_id`` / ``device_id_fetched_at`` (optional): filled in automatically.
"""

import base64
import binascii
import json
import logging
import pathlib
import re
import time

from ofscraper.sites.fansly import constants

log = logging.getLogger("shared")

FIELDS = ("authorization_token", "user_agent", "check_key", "device_id", "device_id_fetched_at")
PLACEHOLDER = "ReplaceMe"
_cache = {"path": None, "mtime": None, "auth": None}


def empty() -> dict:
    return {
        "authorization_token": "",
        "user_agent": "",
        "check_key": "",
        "device_id": "",
        "device_id_fetched_at": 0,
    }


def auth_path() -> pathlib.Path:
    import ofscraper.utils.paths.common as common_paths

    return common_paths.get_profile_path() / constants.AUTH_FILE


def _clean(value) -> str:
    value = "" if value is None else str(value)
    return re.sub(r"\s+", "", value) if value else ""


def normalize(raw: dict) -> dict:
    auth = empty()
    raw = raw or {}
    token = _clean(raw.get("authorization_token") or raw.get("authorization") or raw.get("token"))
    if token.lower().startswith("bearer"):
        token = token[len("bearer"):]
    auth["authorization_token"] = token
    auth["user_agent"] = (raw.get("user_agent") or "").strip()
    auth["check_key"] = _clean(raw.get("check_key"))
    auth["device_id"] = _clean(raw.get("device_id"))
    try:
        auth["device_id_fetched_at"] = float(raw.get("device_id_fetched_at") or 0)
    except (TypeError, ValueError):
        auth["device_id_fetched_at"] = 0
    return auth


def problems(auth: dict) -> list:
    """Reasons the auth can't be used; empty when it looks usable."""
    out = []
    token = auth.get("authorization_token") or ""
    ua = auth.get("user_agent") or ""
    if len(token) < 50 or token == PLACEHOLDER:
        out.append("authorization_token is missing or too short")
    if len(ua) < 40 or ua == PLACEHOLDER:
        out.append("user_agent is missing or too short")
    return out


def read_auth(path=None) -> dict:
    """Auth from the profile's file (missing file gives empty values)."""
    path = pathlib.Path(path or auth_path())
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return empty()
    if _cache["path"] == path and _cache["mtime"] == mtime:
        return dict(_cache["auth"])
    with open(path, encoding="utf-8") as f:
        auth = normalize(json.load(f))
    hide_token(auth.get("authorization_token"))
    _cache.update(path=path, mtime=mtime, auth=dict(auth))
    return auth


def hide_token(token):
    """Mask the token in logs: failed requests log their headers, token included."""
    if not token or token == PLACEHOLDER:
        return
    import ofscraper.utils.logs.utils.sensitive as sensitive

    # the patterns are regexes and a token can hold "+" or "/"
    sensitive.add_sensitive_pattern(re.compile(re.escape(token)), "{fansly_token}")


def write_auth(auth: dict, path=None) -> pathlib.Path:
    path = pathlib.Path(path or auth_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalize(auth), indent=4), encoding="utf-8")
    _cache.update(path=None, mtime=None, auth=None)
    return path


def check_key(auth: dict) -> str:
    return auth.get("check_key") or constants.DEFAULT_CHECK_KEY


def session_id(token: str):
    """Session id carried in the token (base64 of ``<sessionId>:1:2:<hex>``)."""
    if not token:
        return None
    try:
        padded = token + "=" * (-len(token) % 4)
        decoded = base64.b64decode(padded, validate=False).decode("ascii")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    first = decoded.split(":", 1)[0]
    return first if first.isdigit() else None


def device_id_is_fresh(auth: dict, now=None) -> bool:
    now = time.time() if now is None else now
    return bool(auth.get("device_id")) and (
        now - float(auth.get("device_id_fetched_at") or 0)
    ) < constants.DEVICE_ID_MAX_AGE_SECONDS


def store_device_id(device_id: str, path=None, now=None) -> dict:
    auth = read_auth(path)
    auth["device_id"] = _clean(device_id)
    auth["device_id_fetched_at"] = time.time() if now is None else now
    write_auth(auth, path)
    return auth


def make_auth(auth=None) -> dict:
    """Ask for the token and user agent, then save them."""
    import ofscraper.prompts.prompts as prompts
    import ofscraper.utils.settings as settings
    from rich.console import Console

    if settings.get_settings().auth_fail:
        log.info("auth failed quitting on error")
        quit()
    auth = normalize(auth or read_auth())
    console = Console()
    console.print(
        "Fansly needs your authorization token and the browser's user agent.\n"
        "Token: in the browser's devtools on fansly.com, Application > Local Storage >\n"
        "session_active_session > token, or the 'authorization' header of an API request.\n"
        f"They are saved to {auth_path()}",
        style="yellow",
    )
    while True:
        auth["authorization_token"] = _clean(token_prompt(auth.get("authorization_token")))
        auth["user_agent"] = prompts.user_agent_prompt(auth.get("user_agent")).strip()
        issues = problems(auth)
        if not issues:
            break
        console.print("; ".join(issues), style="red")
    write_auth(auth)
    hide_token(auth.get("authorization_token"))
    return auth


def token_prompt(current):
    from InquirerPy.validator import EmptyInputValidator

    import ofscraper.prompts.promptConvert as promptClasses

    name = "input"
    answers = promptClasses.batchConverter(
        {
            "type": "input",
            "name": name,
            "message": "Enter the Fansly authorization token",
            "default": current or "",
            "validate": EmptyInputValidator(),
        }
    )
    return answers[name]


def load() -> dict:
    """Auth for this run; prompts when it is missing or unusable."""
    auth = read_auth()
    if problems(auth):
        log.info("Fansly auth is missing or incomplete")
        auth = make_auth(auth)
    return auth
