"""The debug log doesn't show a media file's signed link.

The normal downloader logged the whole link before each request: the path
(which names the file), the signature, and the account's user id in the
query. Debug logs get pasted into issues. The "download url" line already
went through get_url_log; the "fresh download" and "Downloading media" lines
didn't, and get_url_log itself kept the query.
"""

import asyncio
import logging
from types import SimpleNamespace

import pytest

import ofscraper.commands.scraper.actions.download.managers.main_download as md
import ofscraper.commands.scraper.actions.utils.log as log_utils
from test.test_download_resume import BODY, T, _manager, _quiet, _serve  # noqa: F401

FILENAME = "1920x1080_abcdef0123"
SIGNED = (
    "https://cdn2.onlyfans.com/files/a/ab/abcdef123/"
    f"{FILENAME}.mp4?Tag=2&u=12345&Policy=eyJTdGF0ZW1lbnQ"
    "&Signature=Zx~ab-cd_ef&Key-Pair-Id=K1ABCDEF"
)
SECRETS = [FILENAME, "abcdef123", "u=12345", "eyJTdGF0ZW1lbnQ", "Zx~ab-cd_ef", "K1ABCDEF"]


@pytest.mark.parametrize("have", [0, 300_000], ids=["fresh", "resume"])
def test_download_log_hides_the_link(tmp_path, caplog, have):
    part = tmp_path / "f.part"
    if have:
        part.write_bytes(BODY[:have])
    mgr = _manager(md.MainDownloadManager, [])
    tmp = SimpleNamespace(tempfilepath=part)
    ph = SimpleNamespace(trunicated_filepath=tmp_path / "f.mp4")
    ele = SimpleNamespace(url=SIGNED, mpd=None, id=1, username="u", filename=FILENAME)

    async def run(c):
        if not have:
            await mgr._fresh_data_handler_main(ele, tmp)
        return await mgr._main_download_sendreq(
            c, ele, tmp, placeholderObj=ph, total=T if have else None
        )

    with caplog.at_level(logging.DEBUG):
        total, _, _ = asyncio.run(_serve("range", [], run))
    assert total == T
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "{hidden}" in logged
    for secret in SECRETS:
        assert secret not in logged


def test_link_without_a_query_is_unchanged():
    ele = SimpleNamespace(url="https://cdn2.onlyfans.com/files/a/ab/abc/x.jpeg", mpd=None, filename="x")
    assert log_utils.get_url_log(ele) == "https://cdn2.onlyfans.com/files/a/ab/abc/{hidden}.jpeg"


def test_query_is_hidden():
    ele = SimpleNamespace(url=SIGNED, mpd=None, filename=FILENAME)
    assert log_utils.get_url_log(ele) == (
        "https://cdn2.onlyfans.com/files/a/ab/{hidden}/{hidden}.mp4?{hidden}"
    )
