"""Config menu size and speed prompts: a whole number, then a unit.

File sizes and free space use Bytes / KB / MB / GB (1024-based); the download
speed uses bits/s / Kbps / Mbps / Gbps (1000-based, 8 bits a byte). Values are
still saved in bytes (a second). A value outside the limits, or a min file
size above the max, is refused and asked again. The prompts are scripted:
batchConverter is replaced by a fake that answers from a list.
"""

from types import SimpleNamespace

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.prompts.prompt_groups.config as config_prompts
import ofscraper.prompts.utils.size_prompt as size_prompt
from ofscraper.prompts.utils.size_prompt import SIZE, SPEED

KB, MB, GB = 1024, 1024**2, 1024**3


class _Answers:
    """Answers each prompt by name from a queue; records what was asked."""

    def __init__(self, monkeypatch, answers):
        self.answers = list(answers)
        self.asked = []
        monkeypatch.setattr(size_prompt.promptClasses, "batchConverter", self)
        monkeypatch.setattr(config_prompts.promptClasses, "batchConverter", self)
        monkeypatch.setattr(size_prompt.console, "print", self.printed)
        self.messages = []

    def printed(self, text, *a, **k):
        self.messages.append(text)

    def __call__(self, *questions, **kwargs):
        out = {}
        for q in questions:
            self.asked.append(q)
            name = q["name"]
            if self.answers and self.answers[0][0] == name:
                out[name] = self.answers.pop(0)[1]
            else:  # questions this test doesn't care about keep their default
                out[name] = q.get("default")
        return out


# --- the scales -------------------------------------------------------------


@pytest.mark.parametrize(
    "scale, size, expected",
    [
        (SIZE, 0, (0, MB)),
        (SIZE, 10 * MB, (10, MB)),
        (SIZE, 1500, (1500, 1)),
        (SIZE, None, (0, MB)),
        (SPEED, 0, (0, 1000**2)),
        (SPEED, 12_500_000, (100, 1000**2)),  # 100 Mbps
        (SPEED, 125, (1, 1000)),  # 1 Kbps
        (SPEED, 10 * MB, (83_886_080, 1)),  # an old bytes value, shown exactly
    ],
)
def test_saved_values_open_in_their_largest_exact_unit(scale, size, expected):
    assert scale.split(size) == expected


def test_speed_units_are_bits():
    assert SPEED.to_bytes(100, 1000**2) == 12_500_000
    assert SPEED.to_bytes(1, 1000**3) == 125_000_000
    assert SPEED.format(12_500_000) == "100 Mbps"
    assert [c.name.split()[0] for c in SPEED.choices()] == ["bits/s", "Kbps", "Mbps", "Gbps"]


def test_size_units_are_1024_based():
    assert SIZE.to_bytes(5, GB) == 5 * GB
    assert [c.name.split()[0] for c in SIZE.choices()] == ["Bytes", "KB", "MB", "GB"]


# --- ask_size -------------------------------------------------------------


def _ask(**kw):
    return size_prompt.ask_size(
        "file_size_max", "file_size_max: ", "Files larger than this", kw.pop("current", 0),
        maximum=kw.pop("maximum", 1024**4), **kw
    )


def test_number_then_unit_gives_bytes(monkeypatch):
    answers = _Answers(monkeypatch, [("file_size_max", 50), ("file_size_max_unit", MB)])

    assert _ask() == 50 * MB

    number, unit = answers.asked
    assert number["type"] == "number" and number["min_allowed"] == 0
    assert "Whole numbers only" in number["option_instruction"]
    assert unit["type"] == "list"
    assert [c.value for c in unit["choices"]] == [1, KB, MB, GB]


def test_zero_skips_the_unit_question(monkeypatch):
    answers = _Answers(monkeypatch, [("file_size_max", 0)])

    assert _ask(current=5 * GB) == 0
    assert [q["name"] for q in answers.asked] == ["file_size_max"]


def test_the_current_value_is_the_default(monkeypatch):
    answers = _Answers(monkeypatch, [])

    assert _ask(current=3 * GB) == 3 * GB
    assert answers.asked[0]["default"] == 3
    assert answers.asked[1]["default"] == GB


def test_too_large_is_refused_and_asked_again(monkeypatch):
    answers = _Answers(
        monkeypatch,
        [
            ("file_size_max", 5000),
            ("file_size_max_unit", GB),  # 5000 GB: over 1 TB
            ("file_size_max", 4),
            ("file_size_max_unit", GB),
        ],
    )

    assert _ask(what="The max file size") == 4 * GB
    assert len(answers.messages) == 1
    assert "at most 1 TB" not in answers.messages[0]  # shown in GB, exact
    assert "The max file size can be at most 1,024 GB" in answers.messages[0]
    # the second ask starts from what was typed
    assert answers.asked[2]["default"] == 5000


def test_a_speed_below_the_minimum_is_refused(monkeypatch):
    answers = _Answers(
        monkeypatch,
        [
            ("download_limit", 8),
            ("download_limit_unit", 1),  # 8 bits/s
            ("download_limit", 100),
            ("download_limit_unit", 1000**2),
        ],
    )

    size = size_prompt.ask_size(
        "download_limit", "speed: ", "bits", 0,
        maximum=config_prompts.SPEED_MAX, minimum=config_prompts.SPEED_MIN,
        what="The speed limit", scale=SPEED,
    )

    assert size == 12_500_000
    assert "at least 64 Kbps" in answers.messages[0]


@pytest.mark.parametrize("bits", [1, 5, 7])
def test_a_speed_that_rounds_to_zero_bytes_is_refused_not_saved_as_no_limit(
    monkeypatch, bits
):
    """1 to 7 bits/s is 0 whole bytes a second, and 0 means "no limit"."""
    answers = _Answers(
        monkeypatch,
        [
            ("download_limit", bits),
            ("download_limit_unit", 1),
            ("download_limit", 0),  # then really no limit
        ],
    )

    size = size_prompt.ask_size(
        "download_limit", "speed: ", "bits", 0,
        maximum=config_prompts.SPEED_MAX, minimum=config_prompts.SPEED_MIN,
        what="The speed limit", scale=SPEED,
    )

    assert size == 0
    assert len(answers.messages) == 1
    assert f"{bits} bits/s is too small" in answers.messages[0]
    assert "at least 64 Kbps" in answers.messages[0]
    # asked again: number, unit, number
    assert [q["name"] for q in answers.asked] == [
        "download_limit", "download_limit_unit", "download_limit",
    ]


def test_the_refusal_shows_the_speed_as_typed(monkeypatch):
    """9 bits/s rounds to 1 byte a second; the message says 9 bits/s, not 8."""
    answers = _Answers(
        monkeypatch,
        [("download_limit", 9), ("download_limit_unit", 1), ("download_limit", 0)],
    )
    size_prompt.ask_size(
        "download_limit", "speed: ", "bits", 0,
        maximum=config_prompts.SPEED_MAX, minimum=config_prompts.SPEED_MIN,
        what="The speed limit", scale=SPEED,
    )
    assert "9 bits/s is too small" in answers.messages[0]


# --- the config menus -----------------------------------------------------


@pytest.fixture
def saved(monkeypatch):
    monkeypatch.setattr(config_prompts.config_file, "open_config", lambda: {})
    monkeypatch.setattr(
        config_prompts.schema, "get_current_config_schema", lambda d: d["config"]
    )
    for name, value in {
        "get_filesize_max": 0,
        "get_filesize_min": 0,
        "get_download_limit": 0,
        "get_system_freesize": 0,
        "get_download_semaphores": 6,
    }.items():
        monkeypatch.setattr(config_prompts.data, name, lambda value=value, **k: value)


def test_content_menu_refuses_a_min_above_the_max(monkeypatch, saved):
    answers = _Answers(
        monkeypatch,
        [
            ("file_size_max", 10),
            ("file_size_max_unit", MB),
            ("file_size_min", 20),
            ("file_size_min_unit", MB),  # above the max
            ("file_size_min", 1),
            ("file_size_min_unit", MB),
        ],
    )

    result = config_prompts.content_config()

    assert result["file_size_max"] == 10 * MB
    assert result["file_size_min"] == 1 * MB
    assert "above the max (10 MB)" in answers.messages[0]


def test_performance_menu_saves_the_speed_in_bytes_a_second(monkeypatch, saved):
    _Answers(monkeypatch, [("download_limit", 50), ("download_limit_unit", 1000**2)])

    result = config_prompts.performance_config()

    assert result["download_limit"] == 6_250_000  # 50 Mbps


def test_download_menu_saves_free_space_in_bytes(monkeypatch, saved):
    _Answers(monkeypatch, [("system_free_min", 20), ("system_free_min_unit", GB)])

    result = config_prompts.download_config()

    assert result["system_free_min"] == 20 * GB
