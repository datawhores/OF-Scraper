import ofscraper.utils.auth.data as auth_data


def auth_schema(auth):
    return {
        "sess": auth_data.get_session(auth),
        "auth_id": auth_data.get_id(auth),
        "auth_uid": auth_data.get_uid(auth),
        "user_agent": auth_data.get_user_agent(auth),
        "x-bc": auth_data.x_bc(auth),
    }


def auth_key_missing(auth):
    if "auth" in auth:
        auth = auth["auth"]
    for key in [
        "x-bc",
        "user_agent",
        "auth_id",
        "sess",
    ]:
        if auth.get(key) is None:
            return True
    return False


def auth_key_null(auth):
    if "auth" in auth:
        auth = auth["auth"]
    for key in ["x-bc", "user_agent", "auth_id", "sess"]:
        if auth.get(key) is None or auth.get(key) == "":
            return True
    return False
