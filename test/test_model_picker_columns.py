import asyncio
from types import SimpleNamespace

import pytest
from pfzy import fuzzy_match
from rich.cells import cell_len

import ofscraper.prompts.prompt_groups.model as model_prompt
import ofscraper.prompts.utils.model_helpers as model_helpers
import ofscraper.prompts.utils.prompt_helpers as prompt_helpers


@pytest.fixture
def picker_models(monkeypatch):
    options = dict(
        sort="name",
        renewal=None,
        last_seen=False,
        last_seen_after=None,
        last_seen_before=None,
    )
    for price in ("current", "regular", "renewal", "promo"):
        for suffix in ("", "_min", "_max"):
            options[f"{price}_price{suffix}"] = None
    settings = SimpleNamespace(**options)
    monkeypatch.setattr(model_helpers.settings, "get_settings", lambda: settings)
    names = ["x", "x" * 18, "\u754c" * 10, "e\u0301" * 12]
    models = [
        SimpleNamespace(
            name=f"{names[i % len(names)]}{i}",
            subscribed_string=None if i % 2 else "2025-04-20",
            renewed_string=None if i % 2 else "2025-05-20",
            expired_string=None,
            last_seen=None if i % 2 else "2025-04-21",
            final_current_price=0 if i % 2 else 12.99,
        )
        for i in range(12)
    ]
    return settings, models


@pytest.mark.parametrize(
    "renewal,last_seen", [(False, False), (True, False), (False, True), (True, True)]
)
@pytest.mark.parametrize("entry", ["initial", "refresh"])
def test_picker_columns(monkeypatch, picker_models, renewal, last_seen, entry):
    settings, models = picker_models
    settings.renewal = True if renewal else None
    settings.last_seen = last_seen
    captured = {}
    if entry == "initial":

        def capture(**kwargs):
            captured.update(kwargs)
            return kwargs["choices"]

        monkeypatch.setattr(model_prompt.promptClasses, "getFuzzySelection", capture)
        choices = model_prompt.model_selector(models, [models[0]])
        assert choices[0].enabled
        assert captured["transformer"]([choices[0].name, choices[9].name]) == (
            f"{models[0].name},{models[9].name}"
        )
    else:
        monkeypatch.setattr(
            prompt_helpers.manager,
            "Manager",
            SimpleNamespace(
                current_model_manager=SimpleNamespace(
                    get_models_from_prompt=lambda: dict(enumerate(models))
                )
            ),
        )
        choices = prompt_helpers._get_choices()

    positions = []
    for choice, model in zip(choices, models):
        label = choice.name
        assert choice.value is model
        assert label.split()[1] == model.name
        assert ("end/renewed date:" in label) == renewal
        assert ("last seen:" in label) == last_seen
        positions.append(
            [
                cell_len(label[:label.index(":")]),
                cell_len(label[:label.index("=>")]),
                *[cell_len(label[:i]) for i, char in enumerate(label) if char == "|"],
                cell_len(label),
            ]
        )
    assert all(position == positions[0] for position in positions)

    matches = asyncio.run(
        fuzzy_match(
            models[1].name, [{"name": choice.name} for choice in choices], key="name"
        )
    )
    assert matches
    assert all(models[1].name in match["name"] for match in matches)


def test_empty_picker():
    assert model_helpers.model_selector_choices([]) == []


def test_range_selection_with_padded_numbers(monkeypatch, picker_models):
    _, models = picker_models
    choices = model_helpers.model_selector_choices(models)
    prompt = SimpleNamespace(
        content_control=SimpleNamespace(_raw_choices=choices),
        selected_choices=[{"name": choices[0].name}],
    )
    monkeypatch.setattr(
        prompt_helpers.promptConvert, "multiline_input_prompt", lambda **kwargs: "10"
    )
    result = prompt_helpers._select_helper(prompt)
    assert result[0].enabled
    assert result[9].enabled
    assert sum(choice.enabled for choice in result) == 2
