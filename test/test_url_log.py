from types import SimpleNamespace

import ofscraper.commands.scraper.actions.utils.log as log_utils


def _media(url, filename):
    return SimpleNamespace(url=url, mpd=None, filename=filename)


def test_filename_with_regex_characters_is_hidden():
    # a profile header uploaded as "Untitled design (7).png": Media.filename
    # strips the trailing ")", leaving an unbalanced "(" at position 16
    url = "https://public.onlyfans.com/files/a/ab/abc/123/Untitled design (7).png"
    logged = log_utils.get_url_log(_media(url, "Untitled design (7"))
    assert "Untitled design (7" not in logged and "{hidden}" in logged


def test_ordinary_filename_is_hidden():
    url = "https://cdn2.onlyfans.com/files/a/ab/abc/1000x1800_cb46.jpeg"
    logged = log_utils.get_url_log(_media(url, "1000x1800_cb46"))
    assert "1000x1800_cb46" not in logged
