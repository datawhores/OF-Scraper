"""
Matching -u / --excluded-username names against creator names.

The option callbacks lowercase every name, but Fansly keeps a creator's
capitals ("SomeCreator"), so names are compared without regard to case.
Account ids are compared as strings.
"""


def username_key(name) -> str:
    """The form a username is compared in."""
    return str(name).lower()


def username_keys(names) -> set:
    """Comparison keys for a list of names or ids, skipping empty ones."""
    return {username_key(x) for x in (names or []) if x}


def matches_username(name, keys) -> bool:
    """True if ``name`` is one of ``keys`` (from ``username_keys``)."""
    return bool(name) and username_key(name) in keys


def matches_account(name, account_id, keys) -> bool:
    """True if a username or an account id is one of ``keys``."""
    return matches_username(name, keys) or (
        account_id is not None and str(account_id) in keys
    )


def model_matches(model, keys) -> bool:
    """True if a model's username or account id is one of ``keys``."""
    return matches_account(model.name, model.id, keys)


def select_models(models, names):
    """
    Models named by ``names`` (usernames or account ids), in ``models``' order,
    and the names that matched none of them.
    """
    keys = username_keys(names)
    selected = [m for m in models if model_matches(m, keys)]
    found = set()
    for m in selected:
        found.add(username_key(m.name))
        found.add(str(m.id))
    unmatched = [x for x in (names or []) if x and username_key(x) not in found]
    return selected, unmatched
