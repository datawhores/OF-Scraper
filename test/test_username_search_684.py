"""-fi / -fl pick how --username creators are found (#684).

The mode check compared against a misspelt "indvidual", so -fi was ignored
and the subscription counts decided instead.
"""

import asyncio
from types import SimpleNamespace

import pytest

import ofscraper.data.models.utils.retriver as retriver
from ofscraper.utils.args.parse.commands.main import program


def _parse(args):
    params, _ = program.main(args=args, standalone_mode=False, prog_name="OF-Scraper")
    return params


@pytest.mark.parametrize(
    "args, expected",
    [(["-fi"], "individual"), (["-fl"], "list"), ([], None)],
    ids=["fi", "fl", "neither"],
)
def test_flags_set_username_search(args, expected):
    assert _parse(args)["username_search"] == expected


def _run(monkeypatch, usernames, count, username_search):
    used = []

    async def individual():
        used.append("individual")
        return []

    async def via_list(_count):
        used.append("list")
        return []

    monkeypatch.setattr(retriver.sites, "is_fansly", lambda: False)
    monkeypatch.setattr(retriver, "get_sub_count", lambda: count)
    monkeypatch.setattr(retriver, "get_via_individual", individual)
    monkeypatch.setattr(retriver, "get_via_list", via_list)
    monkeypatch.setattr(
        retriver.settings,
        "get_settings",
        lambda: SimpleNamespace(
            anon=False, usernames=usernames, username_search=username_search
        ),
    )
    asyncio.run(retriver.get_models())
    return used


# 3 names, 12 subscriptions: the count rule picks list
FEW_SUBS = [10, 2]
# 1 name, 120 subscriptions: the count rule picks individual
MANY_SUBS = [100, 20]


def test_fi_uses_individual_when_counts_pick_list(monkeypatch):
    names = ["a", "b", "c"]
    assert _run(monkeypatch, names, FEW_SUBS, "individual") == ["individual"]


def test_fl_uses_list_when_counts_pick_individual(monkeypatch):
    assert _run(monkeypatch, ["a"], MANY_SUBS, "list") == ["list"]


@pytest.mark.parametrize(
    "names, count, expected",
    [
        (["a", "b", "c"], FEW_SUBS, ["list"]),
        (["a"], MANY_SUBS, ["individual"]),
    ],
    ids=["counts-pick-list", "counts-pick-individual"],
)
def test_neither_flag_counts_decide(monkeypatch, names, count, expected):
    assert _run(monkeypatch, names, count, None) == expected
