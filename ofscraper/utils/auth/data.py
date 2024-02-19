import re


def get_session(auth):
    val = None
    if auth.get("sess"):
        val = auth.get("sess")
    cookie = auth.get("auth", {}).get("cookie") or auth.get("cookie")
    if cookie:
        val = (
            next(filter(lambda x: x.find("sess") != -1, cookie.split(";")), "") or ""
        ).replace("sess=", "")
    return fix_val(val)


def get_id(auth):
    val = None
    if auth.get("auth_id"):
        val = auth.get("auth_id")
    cookie = auth.get("auth", {}).get("cookie") or auth.get("cookie")
    if cookie:
        val = (
            next(filter(lambda x: x.find("auth_id") != -1, cookie.split(";")), "") or ""
        ).replace("auth_id=", "")
    return fix_val(val)


def get_uid(auth):
    val = None
    if auth.get("auth_uid"):
        val = auth.get("auth_uid")
    elif auth.get("auth_uid_"):
        val = auth.get("auth_uid_")
    cookie = auth.get("auth", {}).get("cookie") or auth.get("cookie")
    if cookie:
        val = (
            next(filter(lambda x: x.find("auth_uid") != -1, cookie.split(";")), "")
            or ""
        )
        val = val.replace("auth_uid", "")
        val = re.sub("[=_]", "", val)
    return fix_val(val)


def x_bc(auth):
    val = (
        auth.get("x_bc")
        or auth.get("x-bc")
        or auth.get("auth", {}).get("x-bc")
        or auth.get("auth", {}).get("x_bc")
        or ""
    )
    return fix_val(val)


def get_user_agent(auth):
    val = auth.get("user_agent", "") or ""
    return fix_val(val)


def fix_val(value):
    value = value or ""
    value = value.strip()
    re.sub("^ +", "", value)
    value = re.sub(" +$", "", value)
    value = re.sub("\n+", "", value)
    return value
