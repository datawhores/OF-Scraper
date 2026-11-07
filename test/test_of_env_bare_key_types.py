"""A setting set under its bare key name must come back as the right type.

of_env.getattr checks os.environ[key] first and returned the raw text, so
DOWNLOAD_NUM_TRIES=2 came back as "2" and CDM_FORCE_KEY=False as "False",
which is truthy (#174, item 4). For 36 keys the bare name is also the
documented variable the loader reads, so this hit documented settings too.
"""

import logging

import pytest

import ofscraper.utils.of_env.of_env as of_env


@pytest.mark.parametrize(
    "key, text, expected",
    [
        ("DOWNLOAD_NUM_TRIES", "2", 2),  # int
        ("OF_MIN_WAIT_API", "0.5", 0.5),  # float
        ("OF_MIN_WAIT_API", "2", 2.0),  # an int written for a float
        ("CDM_FORCE_KEY", "False", False),  # bool
        ("CDM_FORCE_KEY", "1", True),
        ("API_FORCE_KEY", "TRUE", True),
        ("FILTER_DEFAULT", "Images, Videos", ["Images", "Videos"]),  # list
        ("FILTER_DEFAULT", '["Images", "Videos"]', ["Images", "Videos"]),
        ("SUPRESS_OUTPUTS", "ERROR,OFF", {"ERROR", "OFF"}),  # set
        ("EMPTY_MEDIA_DEFAULT", '{"a": 1}', {"a": 1}),  # dict, as JSON
        ("QUALITY_UNKNOWN_DEFAULT", "720", "720"),  # str stays text
    ],
)
def test_bare_key_is_converted_to_the_default_type(monkeypatch, key, text, expected):
    monkeypatch.setenv(key, text)
    value = of_env.getattr(key)
    assert value == expected
    assert type(value) is type(expected)


def test_bad_value_falls_back_to_the_configured_value(monkeypatch):
    configured = of_env.getattr("DOWNLOAD_NUM_TRIES")
    monkeypatch.setenv("DOWNLOAD_NUM_TRIES", "lots")
    assert of_env.getattr("DOWNLOAD_NUM_TRIES") == configured


def test_bad_value_is_warned_about_once(monkeypatch):
    warnings = []
    monkeypatch.setattr(logging.getLogger("shared"), "warning", warnings.append)
    monkeypatch.setenv("DOWNLOAD_NUM_TRIES", "many")
    for _ in range(5):
        of_env.getattr("DOWNLOAD_NUM_TRIES")
    assert len(warnings) == 1, warnings
    # a different bad value is a new warning
    monkeypatch.setenv("DOWNLOAD_NUM_TRIES", "several")
    of_env.getattr("DOWNLOAD_NUM_TRIES")
    assert len(warnings) == 2, warnings


def test_unknown_key_is_returned_as_text(monkeypatch):
    monkeypatch.setenv("OFSC_TEST_NOT_A_SETTING", "5")
    assert of_env.getattr("OFSC_TEST_NOT_A_SETTING") == "5"
