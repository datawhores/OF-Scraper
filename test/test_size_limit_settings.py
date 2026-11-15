"""size_min / size_max: 0 set in the cart sidebar means no limit.

The sidebar writes 0 for an empty box. Merging used ``args.size_max or
config``, so a 0 fell back to the config's limit and the box looked ignored.
Only an unset value (None, the CLI default) should fall back.
"""

import pytest

import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.config.data as config_data
import ofscraper.utils.settings as settings

CONFIG_MAX = 500 * 1024**2
CONFIG_MIN = 1024**2


@pytest.fixture
def merge(monkeypatch):
    monkeypatch.setattr(config_data, "get_filesize_max", lambda *a, **k: CONFIG_MAX)
    monkeypatch.setattr(config_data, "get_filesize_min", lambda *a, **k: CONFIG_MIN)

    def run(size_min, size_max):
        args = settings.get_args(copy=True)
        args.size_min = size_min
        args.size_max = size_max
        monkeypatch.setattr(read_args, "retriveArgs", lambda: args)
        merged = settings.merged_settings()
        return merged.size_min, merged.size_max

    return run


def test_zero_overrides_the_config_limit(merge):
    assert merge(0, 0) == (0, 0)


def test_a_value_overrides_the_config_limit(merge):
    assert merge(2048, 4096) == (2048, 4096)


def test_unset_falls_back_to_the_config(merge):
    assert merge(None, None) == (CONFIG_MIN, CONFIG_MAX)
