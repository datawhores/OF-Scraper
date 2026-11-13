"""get_styled() shows a cell whose value isn't a str, bool, int or list
(e.g. None) instead of raising."""

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.classes.table.sections.table as table


@pytest.mark.parametrize(
    "canview,want_unlocked,want_cart",
    [(None, False, "Not Unlocked"), (True, True, "[]"), (False, False, "Not Unlocked")],
)
def test_unlocked_cell_agrees_with_cart(canview, want_unlocked, want_cart):
    from types import SimpleNamespace

    import ofscraper.commands.check as check

    ele = SimpleNamespace(canview=canview)
    assert check.unlocked_helper(ele) is want_unlocked
    assert check.checkmarkhelper(ele) == want_cart


@pytest.mark.parametrize("value", [None, 1.5, {"a": 1}])
def test_other_value_types_are_shown(monkeypatch, value):
    monkeypatch.setattr(table, "get_col_names", lambda: ["unlocked", "media_id"])
    row = {"unlocked": value, "media_id": 7}
    cells = table.get_styled(row)
    assert [c.plain for c in cells] == [str(value), "7"]
    assert str(cells[0].style) == "bold white"
