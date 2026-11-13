"""Merge DB's checks the source folder before touching the target (#310).

A missing source, or a source that is a file, must fail with an error naming
the path, and leave nothing behind in the target folder: no new database, no
backup folder, no parent folders.
"""

import asyncio

import pytest

import ofscraper.db.merge as merge


def make_source(tmp_path, kind):
    source = tmp_path / "source"
    if kind == "file":
        source.write_text("not a folder")
    return source


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_bad_source_creates_no_target_folder(tmp_path, kind):
    source = make_source(tmp_path, kind)
    target = tmp_path / "target" / "nested"

    with pytest.raises(FileNotFoundError) as error:
        asyncio.run(merge.MergeDatabase()(source, target / "user_data.db"))

    assert str(source) in str(error.value)
    assert not (tmp_path / "target").exists()


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_bad_source_leaves_existing_target_folder_empty(tmp_path, kind):
    source = make_source(tmp_path, kind)
    target = tmp_path / "target"
    target.mkdir()

    with pytest.raises(FileNotFoundError) as error:
        asyncio.run(merge.MergeDatabase()(source, target))

    assert str(source) in str(error.value)
    assert list(target.iterdir()) == []
