"""rename_to_format (#764) on a user_data.db. Every file it renames is a
small one made here, under pytest's tmp_path, and the database is a real
one made with the scraper's own tables."""

import asyncio
import contextlib
import json
import os
import sqlite3
import subprocess
import sys
import unicodedata
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.rename_to_format as tool
import ofscraper.db.postgres as postgres
from ofscraper.classes.of.media import Media
from ofscraper.classes.of.posts import Post
from ofscraper.db.operations_.labels import labelsCreate
from ofscraper.db.operations_.media import mediaCreate
from ofscraper.db.operations_.messages import messagesCreate
from ofscraper.db.operations_.others import schemaCreate, siteInsert
from ofscraper.db.operations_.posts import postCreate
from ofscraper.db.operations_.profile import profilesCreate
from ofscraper.db.operations_.stories import storiesCreate

ROOT = Path(__file__).resolve().parents[1]
CREATOR = 10
NAME = "alice"
OLD_DIRS = "{model_username}/{responsetype}/{mediatype}/"
OLD_FILES = "{filename}.{ext}"


@pytest.fixture(autouse=True)
def no_url(monkeypatch):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)


class Library:
    """A creator's user_data.db, the scraper's config.json and the folder
    their files are in."""

    def __init__(self, tmp_path, site=None, names=((NAME, "2025-06-11T10:20:30+00:00"),)):
        self.tmp = tmp_path
        self.root = tmp_path / "media"
        self.root.mkdir()
        self.config = tmp_path / "config" / "config.json"
        self.config.parent.mkdir()
        self.formats(OLD_DIRS, OLD_FILES)
        self.db = tmp_path / ".data" / str(CREATOR) / "user_data.db"
        self.db.parent.mkdir(parents=True)
        self.count = 0
        with closing(sqlite3.connect(self.db)) as conn, conn:
            for create in (mediaCreate, postCreate, messagesCreate, storiesCreate, labelsCreate,
                           profilesCreate, schemaCreate):
                conn.execute(create)
            if site:
                conn.execute(siteInsert, (site,))
            conn.executemany(
                "INSERT INTO profiles (user_id, username, first_seen_at, last_seen_at) VALUES (?,?,?,?)",
                [(CREATOR, name, last, last) for name, last in names],
            )

    def formats(self, dir_format, file_format, **more):
        options = {"save_location": str(self.root), "dir_format": dir_format,
                   "file_format": file_format, "date": "YYYY-MM-DD", **more}
        self.config.write_text(json.dumps({"file_options": options}), encoding="utf-8")

    def post(self, post_id, table="posts", text="a caption", price=0, date="2024-05-06T07:08:09+00:00"):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                f"INSERT INTO {table} (post_id, text, price, archived, created_at, model_id) VALUES (?,?,?,?,?,?)",
                (post_id, text, price, 0, date, CREATOR),
            )

    def add(self, filename, folder="alice/Posts/Images", link=None, post_id=None, area="Timeline",
            kind="Images", posted_at="2024-05-06T07:08:09+00:00", content=None, on_disk=True,
            downloaded=1, media_id=None):
        """A media row that records `filename` in `folder` (under the media
        folder), and the file itself. Returns the file's path."""
        self.count += 1
        media_id = media_id or self.count
        path = self.root / folder / filename
        content = f"content of media {self.count}".encode() if content is None else content
        if on_disk:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        stem = Path(filename).stem
        link = link if link is not None else f"https://cdn.example/files/x/y/{stem}.{Path(filename).suffix[1:]}?Tag=1"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "INSERT INTO medias (media_id, post_id, link, directory, filename, size, api_type, media_type,"
                " downloaded, created_at, posted_at, model_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (media_id, post_id or 500 + self.count, link, str(path.parent), filename, len(content), area, kind,
                 downloaded, posted_at, posted_at, CREATOR),
            )
        return path

    def rows(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute("SELECT media_id, directory, filename FROM medias ORDER BY id").fetchall()

    def run(self, *args, apply=False):
        return tool.rename(self.db, apply=apply, config=self.config, **dict(args))

    def files(self):
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file())


def test_a_preview_lists_the_new_names_and_changes_nothing(tmp_path):
    library = Library(tmp_path)
    library.post(501)
    path = library.add("abcdef.jpg", post_id=501)
    library.formats(OLD_DIRS, "{date}_{filename}.{ext}")
    rows = library.rows()

    result = library.run()

    assert result["to_rename"] == 1 and not result["applied"]
    assert result["renames"] == [{"from": str(path), "to": str(path.with_name("2024-05-06_abcdef.jpg"))}]
    assert library.files() == ["alice/Posts/Images/abcdef.jpg"]
    assert library.rows() == rows
    assert list(library.db.parent.iterdir()) == [library.db]


def test_apply_renames_records_the_new_names_and_writes_the_undo_file_first(tmp_path, monkeypatch):
    library = Library(tmp_path)
    library.post(501)
    path = library.add("abcdef.jpg", post_id=501)
    library.formats("{model_username}/{date}/", "{post_id}_{filename}.{ext}")
    seen = []
    real = tool.rename_file

    def rename_file(old, new):
        # the undo file names the rename before it is made
        (undo_file,) = library.db.parent.glob("*.rename-undo-*.json")
        seen.append(json.loads(undo_file.read_text(encoding="utf-8"))["files"][0]["to"])
        real(old, new)

    monkeypatch.setattr(tool, "rename_file", rename_file)
    result = library.run(apply=True)

    new = library.root / "alice" / "2024-05-06" / "501_abcdef.jpg"
    assert seen == [str(new)]
    assert result["renamed"] == 1 and result["rows_changed"] == 1
    assert library.files() == ["alice/2024-05-06/501_abcdef.jpg"]
    assert new.read_bytes() == b"content of media 1"
    assert library.rows() == [(1, str(new.parent), new.name)]
    # the emptied old folders go; alice holds the new one
    assert result["folders_removed"] == [str(path.parent), str(path.parent.parent)]
    assert library.root.is_dir()
    assert Path(result["undo_file"]).is_file()

    # a second run finds nothing to do
    again = library.run(apply=True)
    assert again["unchanged"] == 1 and again["to_rename"] == 0 and again["undo_file"] is None


def test_undo_puts_back_the_names_and_the_rows(tmp_path):
    library = Library(tmp_path)
    library.post(501)
    library.add("abcdef.jpg", post_id=501)
    library.add("other.jpg", post_id=501)
    rows = library.rows()
    library.formats("{model_username}/All/", "{media_id}.{ext}")
    undo_file = library.run(apply=True)["undo_file"]
    assert library.files() == ["alice/All/1.jpg", "alice/All/2.jpg"]

    preview = tool.undo(undo_file)
    assert (preview["files_to_rename_back"], preview["rows_to_restore"]) == (2, 2)
    assert library.files() == ["alice/All/1.jpg", "alice/All/2.jpg"]

    done = tool.undo(undo_file, apply=True)
    assert (done["renamed_back"], done["rows_restored"]) == (2, 2)
    assert library.files() == ["alice/Posts/Images/abcdef.jpg", "alice/Posts/Images/other.jpg"]
    assert library.rows() == rows
    # a second undo changes nothing
    assert tool.undo(undo_file, apply=True)["rows_restored"] == 0
    assert library.rows() == rows


def test_an_undo_whose_row_update_fails_gives_the_files_their_new_names_back(tmp_path):
    library = Library(tmp_path)
    library.post(501)
    library.add("abcdef.jpg", post_id=501)
    library.add("other.jpg", post_id=501)
    rows = library.rows()
    library.formats("{model_username}/All/", "{media_id}.{ext}")
    undo_file = library.run(apply=True)["undo_file"]
    renamed = library.rows()
    with closing(sqlite3.connect(library.db)) as conn, conn:
        # the second file's row can't be given its old name back
        conn.execute(
            "CREATE TRIGGER refuse BEFORE UPDATE ON medias WHEN NEW.filename = 'other.jpg'"
            " BEGIN SELECT RAISE(ABORT, 'refused'); END"
        )

    with pytest.raises(sqlite3.IntegrityError):
        tool.undo(undo_file, apply=True)

    # the first file's rename back is reversed with the rolled back rows
    assert library.files() == ["alice/All/1.jpg", "alice/All/2.jpg"]
    assert library.rows() == renamed

    with closing(sqlite3.connect(library.db)) as conn, conn:
        conn.execute("DROP TRIGGER refuse")
    done = tool.undo(undo_file, apply=True)
    assert (done["renamed_back"], done["rows_restored"]) == (2, 2)
    assert library.files() == ["alice/Posts/Images/abcdef.jpg", "alice/Posts/Images/other.jpg"]
    assert library.rows() == rows


@contextlib.contextmanager
def read_lock(db):
    """Another connection reading the database, as a scan or a viewer can:
    a commit then waits, and fails with "database is locked"."""
    with closing(sqlite3.connect(db, isolation_level=None)) as reader:
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM medias").fetchone()
        yield
        reader.execute("ROLLBACK")


def test_an_undo_whose_commit_fails_gives_the_files_their_new_names_back(tmp_path):
    library = Library(tmp_path)
    library.post(501)
    library.add("abcdef.jpg", post_id=501)
    library.add("other.jpg", post_id=501)
    rows = library.rows()
    library.formats("{model_username}/All/", "{media_id}.{ext}")
    undo_file = library.run(apply=True)["undo_file"]
    renamed = library.rows()

    with read_lock(library.db), pytest.raises(sqlite3.OperationalError, match="locked"):
        tool.undo(undo_file, apply=True)

    # nothing was saved, so the files keep the names their rows still record
    assert library.rows() == renamed
    assert library.files() == ["alice/All/1.jpg", "alice/All/2.jpg"]

    done = tool.undo(undo_file, apply=True)
    assert (done["renamed_back"], done["rows_restored"]) == (2, 2)
    assert library.files() == ["alice/Posts/Images/abcdef.jpg", "alice/Posts/Images/other.jpg"]
    assert library.rows() == rows


def test_an_apply_whose_commit_fails_gives_the_files_their_old_names_back(tmp_path):
    library = Library(tmp_path)
    library.post(501)
    library.add("abcdef.jpg", post_id=501)
    library.add("other.jpg", post_id=501)
    rows = library.rows()
    library.formats("{model_username}/All/", "{media_id}.{ext}")

    with read_lock(library.db), pytest.raises(sqlite3.OperationalError, match="locked"):
        library.run(apply=True)

    # nothing was saved: the files are where their rows say, so the undo
    # file has nothing to put back and is removed
    assert library.rows() == rows
    assert library.files() == ["alice/Posts/Images/abcdef.jpg", "alice/Posts/Images/other.jpg"]
    assert list(Path(library.db).parent.glob("*.rename-undo-*")) == []

    assert library.run(apply=True)["rows_changed"] == 2
    assert library.files() == ["alice/All/1.jpg", "alice/All/2.jpg"]


class _CommitThenStop:
    """A connection whose commit goes through and is then interrupted, as a
    Ctrl+C landing just after it would be."""

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def commit(self):
        self._conn.commit()
        raise KeyboardInterrupt

    def close(self):
        self._conn.close()


def interrupt_after_commit(monkeypatch):
    real = tool._connect
    monkeypatch.setattr(tool, "_connect", lambda *a: _CommitThenStop(real(*a)))


def test_an_apply_stopped_after_its_commit_keeps_the_new_names(tmp_path, monkeypatch):
    # the rows were saved: moving the files back would part them from their rows
    library = Library(tmp_path)
    library.post(501)
    library.add("abcdef.jpg", post_id=501)
    library.add("other.jpg", post_id=501)
    library.formats("{model_username}/All/", "{media_id}.{ext}")
    interrupt_after_commit(monkeypatch)

    with pytest.raises(postgres.Unconfirmed):
        library.run(apply=True)

    assert library.files() == ["alice/All/1.jpg", "alice/All/2.jpg"]
    assert [row[1:3] for row in library.rows()][0][1] == "1.jpg"
    assert list(Path(library.db).parent.glob("*.rename-undo-*"))  # kept, to undo with


def test_an_undo_stopped_after_its_commit_keeps_the_old_names(tmp_path, monkeypatch, capsys):
    library = Library(tmp_path)
    library.post(501)
    library.add("abcdef.jpg", post_id=501)
    rows = library.rows()
    library.formats("{model_username}/All/", "{media_id}.{ext}")
    undo_file = library.run(apply=True)["undo_file"]
    interrupt_after_commit(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        tool.undo(undo_file, apply=True)

    assert library.rows() == rows
    assert library.files() == ["alice/Posts/Images/abcdef.jpg"]
    assert "isn't known whether they were" in capsys.readouterr().err


def test_names_match_what_the_download_code_builds(tmp_path):
    """The rows are written as a download writes them, from the scraper's
    own Post and Media, and the new names are those the same code gives
    under the new formats."""
    library = Library(tmp_path)
    api_post = {"id": 777, "postedAt": "2024-02-03T04:05:06+00:00", "price": 0, "text": "Hello <b>there</b> you",
                "responseType": "post", "media": [
                    {"id": 11, "type": "photo", "canView": True, "createdAt": "2024-02-01T00:00:00+00:00",
                     "files": {"full": {"url": "https://cdn.example/files/a/b/0abc123_photo.jpg?Tag=2"}}},
                    {"id": 12, "type": "video", "canView": True,
                     "source": {"source": "https://cdn.example/files/a/b/9xyz_source.mp4?Tag=3"}},
                ]}
    library.post(777, text=api_post["text"], date=api_post["postedAt"])

    def download_paths():
        post = Post(api_post, CREATOR, NAME, responsetype="timeline")
        out = []
        with tool.scraper_settings(config=library.config), tool._offline(placeholder):
            for media, ext in zip(post.media, ("jpg", "mp4")):
                names = asyncio.run(placeholder.Placeholders(media, ext).init(create=False))
                out.append((media, names.trunicated_filepath))
        return out

    for media, path in download_paths():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"data")
        with closing(sqlite3.connect(library.db)) as conn, conn:
            conn.execute(
                "INSERT INTO medias (media_id, post_id, link, directory, filename, size, api_type, media_type,"
                " downloaded, created_at, posted_at, model_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (media.id, media.post_id, media.link, str(path.parent), path.name, 4,
                 media.responsetype.capitalize(), media.mediatype.capitalize(), 1, media.date, media.postdate, CREATOR),
            )
    library.formats("{model_username}/{value}/{response_type}-{media_type}/{date}/",
                    "{text}_{media_id}_{only_filename}_{quality}_{filename}.{ext}", text_length=2)
    expected = sorted(str(path) for _media, path in download_paths())

    result = library.run(apply=True)

    assert result["left"] == [] and result["renamed"] == 2
    assert sorted(str(Path(d, f)) for _id, d, f in library.rows()) == expected
    assert sorted(str(library.root / f) for f in library.files()) == expected


def test_a_name_that_needs_a_value_the_database_lacks_is_left(tmp_path):
    library = Library(tmp_path)
    library.post(501)
    image = library.add("abcdef.jpg", post_id=501)
    # the old name doesn't show the video's quality
    video = library.add("clip.mp4", folder="alice/Posts/Videos", post_id=502, kind="Videos",
                        link="https://cdn.example/files/x/clip_source.mp4")
    story = library.add("story.jpg", folder="alice/Stories/Images", post_id=503, area="Stories")
    library.post(503, table="stories", text="title")
    library.formats(OLD_DIRS, "{text}_{quality}_{current_price}.{ext}")

    result = library.run(apply=True)

    left = {entry["file"]: entry["why"] for entry in result["left"]}
    assert left == {
        str(image): tool.NEEDS.format("{current_price}"),
        str(video): tool.NEEDS.format("{current_price}, {quality}, {text}"),
        str(story): tool.NEEDS.format("{current_price}, {text}"),
    }
    assert result["renamed"] == 0 and result["undo_file"] is None
    assert library.files() == ["alice/Posts/Images/abcdef.jpg", "alice/Posts/Videos/clip.mp4",
                               "alice/Stories/Images/story.jpg"]


def test_a_count_is_only_given_to_a_post_with_one_media(tmp_path):
    library = Library(tmp_path)
    library.post(501)
    single = library.add("a.jpg", post_id=501)
    first = library.add("b.jpg", post_id=600)
    library.add("c.jpg", post_id=600)
    library.formats(OLD_DIRS, "{post_id}.{ext}")

    result = library.run()

    assert result["renames"] == [{"from": str(single), "to": str(single.with_name("501.jpg"))}]
    assert {entry["file"] for entry in result["left"]} == {str(first), str(first.with_name("c.jpg"))}
    assert all(entry["why"] == tool.NEEDS.format("{count}") for entry in result["left"])


def test_an_existing_file_at_the_new_place_is_never_replaced(tmp_path):
    library = Library(tmp_path)
    path = library.add("abcdef.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    stranger = path.with_name("1.jpg")
    stranger.write_bytes(b"not ours")

    result = library.run(apply=True)

    assert result["left"] == [{"file": str(path), "why": tool.TAKEN, "new_place": str(stranger)}]
    assert stranger.read_bytes() == b"not ours"
    assert path.read_bytes() == b"content of media 1"
    assert library.rows()[0][2] == "abcdef.jpg"


def test_a_place_taken_while_it_runs_is_not_replaced(tmp_path, monkeypatch):
    library = Library(tmp_path)
    path = library.add("abcdef.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    real = tool.rename_file

    def someone_writes_first(old, new):
        Path(new).write_bytes(b"written meanwhile")
        real(old, new)

    monkeypatch.setattr(tool, "rename_file", someone_writes_first)
    result = library.run(apply=True)

    assert result["renamed"] == 0
    assert result["left"][0]["file"] == str(path) and "could not be renamed" in result["left"][0]["why"]
    assert path.with_name("1.jpg").read_bytes() == b"written meanwhile"
    assert path.read_bytes() == b"content of media 1"
    assert library.rows()[0][2] == "abcdef.jpg"


def test_files_that_would_get_one_name_are_all_left(tmp_path):
    library = Library(tmp_path)
    library.post(501)
    library.post(502)
    first = library.add("a.jpg", post_id=501)
    second = library.add("b.jpg", post_id=502)
    library.formats(OLD_DIRS, "{date}.{ext}")

    result = library.run(apply=True)

    assert sorted(entry["file"] for entry in result["left"]) == [str(first), str(second)]
    assert {entry["why"] for entry in result["left"]} == {tool.SAME_TARGET}
    assert library.files() == ["alice/Posts/Images/a.jpg", "alice/Posts/Images/b.jpg"]


def test_a_new_place_another_row_records_is_left(tmp_path):
    library = Library(tmp_path)
    moving = library.add("abcdef.jpg")
    # the row of a file that is gone records the place this one would get
    library.add("1.jpg", on_disk=False, downloaded=0, media_id=99)
    library.formats(OLD_DIRS, "{media_id}.{ext}")

    result = library.run(apply=True)

    assert {"file": str(moving), "why": tool.RECORDED, "new_place": str(moving.with_name("1.jpg"))} in result["left"]
    assert moving.is_file()


def test_rows_that_name_one_file_differently_leave_it(tmp_path):
    library = Library(tmp_path)
    path = library.add("shared.jpg", post_id=501, media_id=5)
    # the same media in another post records the same file
    library.add("shared.jpg", post_id=502, media_id=5, on_disk=False)
    library.formats(OLD_DIRS, "{post_id}.{ext}")

    result = library.run(apply=True)

    assert result["left"] == [{"file": str(path), "why": tool.DIFFER,
                               "new_names": [str(path.with_name("501.jpg")), str(path.with_name("502.jpg"))]}]
    assert path.is_file()


def test_rows_that_agree_on_one_file_are_all_changed(tmp_path):
    library = Library(tmp_path)
    path = library.add("shared.jpg", post_id=501, media_id=5)
    library.add("shared.jpg", post_id=502, media_id=5, on_disk=False)
    library.formats(OLD_DIRS, "{media_id}.{ext}")

    result = library.run(apply=True)

    assert result["renamed"] == 1 and result["rows_changed"] == 2
    assert [row[2] for row in library.rows()] == ["5.jpg", "5.jpg"]
    assert path.with_name("5.jpg").is_file()


def test_a_run_that_stopped_is_finished_by_running_it_again(tmp_path):
    library = Library(tmp_path)
    moved = library.add("abcdef.jpg")
    gone = library.add("gone.jpg", on_disk=False)
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    # renamed by a run that stopped before its rows were saved
    moved.rename(moved.with_name("1.jpg"))

    result = library.run(apply=True)

    assert result["already_there"] == 1 and result["rows_changed"] == 1
    assert result["left"] == [{"file": str(gone), "why": tool.NOT_FOUND}]
    assert library.rows()[0][2] == "1.jpg"


def test_a_file_at_the_new_place_with_another_size_is_left(tmp_path):
    library = Library(tmp_path)
    path = library.add("abcdef.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    path.unlink()
    path.with_name("1.jpg").write_bytes(b"something else entirely")

    result = library.run(apply=True)

    assert result["left"][0]["why"] == tool.OTHER_SIZE
    assert library.rows()[0][2] == "abcdef.jpg"


@pytest.mark.skipif(not hasattr(os, "link") or os.name == "nt", reason="hard links where a rename is made with one")
def test_a_link_left_by_a_stopped_rename_is_finished(tmp_path):
    library = Library(tmp_path)
    path = library.add("abcdef.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    os.link(path, path.with_name("1.jpg"))

    result = library.run(apply=True)

    assert result["renamed"] == 1 and result["left"] == []
    assert library.files() == ["alice/Posts/Images/1.jpg"]


def test_a_rename_that_fails_is_listed_and_the_rest_go_on(tmp_path, monkeypatch):
    library = Library(tmp_path)
    first = library.add("a.jpg")
    library.add("b.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    real = tool.rename_file

    def fails_once(old, new):
        if old == str(first):
            raise PermissionError(13, "Permission denied")
        real(old, new)

    monkeypatch.setattr(tool, "rename_file", fails_once)
    result = library.run(apply=True)

    assert result["renamed"] == 1 and result["to_rename"] == 1
    assert result["left"] == [{"file": str(first), "why": "it could not be renamed (Permission denied)"}]
    assert [row[2] for row in library.rows()] == ["a.jpg", "2.jpg"]


def test_a_stop_part_way_puts_the_files_back_and_changes_no_row(tmp_path, monkeypatch):
    library = Library(tmp_path)
    library.add("a.jpg")
    library.add("b.jpg")
    rows = library.rows()
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    real = tool.rename_file
    calls = []

    def stopped(old, new):
        calls.append(old)
        if len(calls) == 2:
            raise KeyboardInterrupt
        real(old, new)

    monkeypatch.setattr(tool, "rename_file", stopped)
    with pytest.raises(KeyboardInterrupt):
        library.run(apply=True)

    monkeypatch.setattr(tool, "rename_file", real)
    assert library.files() == ["alice/Posts/Images/a.jpg", "alice/Posts/Images/b.jpg"]
    assert library.rows() == rows
    # everything was put back: there is nothing to undo
    assert list(library.db.parent.glob("*.rename-undo-*.json")) == []


def test_a_put_back_that_fails_keeps_the_undo_file(tmp_path, monkeypatch, capsys):
    library = Library(tmp_path)
    library.add("a.jpg")
    library.add("b.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    real = tool.rename_file
    calls = []

    def stopped_then_stuck(old, new):
        calls.append(old)
        if len(calls) == 2:
            raise KeyboardInterrupt
        if len(calls) > 2:
            # the file renamed first can't be given its old name back
            raise PermissionError(13, "Permission denied")
        real(old, new)

    monkeypatch.setattr(tool, "rename_file", stopped_then_stuck)
    with pytest.raises(KeyboardInterrupt):
        library.run(apply=True)

    monkeypatch.setattr(tool, "rename_file", real)
    assert library.files() == ["alice/Posts/Images/1.jpg", "alice/Posts/Images/b.jpg"]
    assert len(list(library.db.parent.glob("*.rename-undo-*.json"))) == 1
    assert "The undo file is kept" in capsys.readouterr().err


def renamed_then_stopped(monkeypatch):
    """A Ctrl+C that lands just after a rename is made, before the code
    after it runs (once: renames after it, putting it back, go through)."""
    real = tool.rename_file
    stopped_once = []

    def stopped(old, new):
        real(old, new)
        if not stopped_once:
            stopped_once.append(old)
            raise KeyboardInterrupt

    monkeypatch.setattr(tool, "rename_file", stopped)
    return real


def test_a_stop_just_after_a_rename_puts_that_file_back_and_removes_the_undo_file(tmp_path, monkeypatch):
    library = Library(tmp_path)
    library.add("a.jpg")
    rows = library.rows()
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    real = renamed_then_stopped(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        library.run(apply=True)

    monkeypatch.setattr(tool, "rename_file", real)
    assert library.files() == ["alice/Posts/Images/a.jpg"]
    assert library.rows() == rows
    assert list(library.db.parent.glob("*.rename-undo-*.json")) == []


def test_a_stop_while_files_are_put_back_keeps_the_undo_file(tmp_path, monkeypatch):
    library = Library(tmp_path)
    library.add("a.jpg")
    library.add("b.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    real = tool.rename_file
    calls = []

    def stopped_twice(old, new):
        calls.append(old)
        real(old, new)
        if len(calls) in (2, 3):
            # the second rename, then the first put-back
            raise KeyboardInterrupt

    monkeypatch.setattr(tool, "rename_file", stopped_twice)
    with pytest.raises(KeyboardInterrupt):
        library.run(apply=True)

    monkeypatch.setattr(tool, "rename_file", real)
    assert len(list(library.db.parent.glob("*.rename-undo-*.json"))) == 1


def test_an_undo_stopped_just_after_a_rename_gives_that_file_its_new_name_again(tmp_path, monkeypatch):
    library = Library(tmp_path)
    library.add("a.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    undo_file = library.run(apply=True)["undo_file"]
    renamed = library.rows()
    real = renamed_then_stopped(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        tool.undo(undo_file, apply=True)

    monkeypatch.setattr(tool, "rename_file", real)
    assert library.files() == ["alice/Posts/Images/1.jpg"]
    assert library.rows() == renamed
    assert Path(undo_file).is_file()


def test_apply_and_undo_are_refused_while_postgresql_is_on(tmp_path, monkeypatch, capsys):
    library = Library(tmp_path)
    library.add("a.jpg")
    rows = library.rows()
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    undo_file = library.run(apply=True)["undo_file"]
    renamed = library.rows()
    monkeypatch.setattr(postgres, "url", lambda: "postgresql://u@localhost/db")

    # a preview still works, on the user_data.db
    assert library.run()["unchanged"] == 1
    with pytest.raises(ValueError, match="PostgreSQL is on"):
        library.run(apply=True)
    with pytest.raises(ValueError, match="PostgreSQL is on"):
        tool.undo(undo_file, apply=True)
    assert tool.undo(undo_file)["files_to_rename_back"] == 1
    with pytest.raises(SystemExit) as exit_:
        tool.main([str(library.db), "--config", str(library.config), "--apply"])
    assert exit_.value.code == 1 and "PostgreSQL is on" in capsys.readouterr().err

    assert library.files() == ["alice/Posts/Images/1.jpg"]
    assert library.rows() == renamed != rows


def test_folders_above_the_save_location_and_folders_with_other_files_stay(tmp_path):
    library = Library(tmp_path)
    path = library.add("abcdef.jpg")
    (path.parent / "notes.txt").write_text("mine", encoding="utf-8")
    library.formats("{model_username}/", "{media_id}.{ext}")

    result = library.run(apply=True)

    assert result["folders_removed"] == []
    assert sorted(library.files()) == ["alice/1.jpg", "alice/Posts/Images/notes.txt"]


def test_fansly_names_use_the_media_id_as_the_download_does(tmp_path):
    library = Library(tmp_path, site="fansly")
    library.root = library.root / "Fansly"
    library.formats(OLD_DIRS, OLD_FILES)
    library.post(501)
    path = library.add("123456789.jpg", post_id=501, media_id=123456789,
                       link="https://cdn.example/fansly/abc/other-name.jpg")
    library.formats("{model_username}/{site_name}/", "{date}_{filename}.{ext}")

    result = library.run()

    assert result["creator"]["site"] == "fansly"
    assert result["renames"] == [{"from": str(path),
                                  "to": str(library.root / "alice" / "Fansly" / "2024-05-06_123456789.jpg")}]


def test_the_username_is_the_name_seen_last_or_the_one_given(tmp_path):
    library = Library(tmp_path, names=(("old", "2023-01-01T00:00:00+00:00"), (NAME, "2025-01-01T00:00:00+00:00")))
    path = library.add("abcdef.jpg", folder="old/Posts/Images")

    assert library.run()["renames"] == [{"from": str(path), "to": str(library.root / "alice/Posts/Images/abcdef.jpg")}]
    assert library.run(("username", "old"))["unchanged"] == 1
    with pytest.raises(ValueError, match="--username: someone"):
        library.run(("username", "someone"))


def test_a_naming_script_is_refused(tmp_path):
    library = Library(tmp_path)
    library.add("abcdef.jpg")
    library.config.write_text(json.dumps({"file_options": {"save_location": str(library.root)},
                                          "advanced_options": {"naming_script": str(tmp_path / "name.py")}}))
    with pytest.raises(ValueError, match="naming_script"):
        library.run(apply=True)
    assert library.files() == ["alice/Posts/Images/abcdef.jpg"]


def test_a_missing_config_is_refused_and_none_is_made(tmp_path):
    library = Library(tmp_path)
    library.add("abcdef.jpg")
    missing = tmp_path / "nowhere" / "config.json"
    with pytest.raises(ValueError, match="no config.json"):
        tool.rename(library.db, config=missing)
    assert not missing.parent.exists()


def test_settings_are_put_back_after_a_run(tmp_path):
    import ofscraper.utils.args.globals as global_args
    import ofscraper.utils.settings as settings

    library = Library(tmp_path)
    library.add("abcdef.jpg")
    before = global_args.args, settings.settings
    library.run()
    assert (global_args.args, settings.settings) == before


def test_the_command_line_previews_applies_and_undoes(tmp_path, capsys):
    library = Library(tmp_path)
    library.add("abcdef.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    common = [str(library.db), "--config", str(library.config)]

    assert tool.main(common) == 0
    assert json.loads(capsys.readouterr().out)["to_rename"] == 1
    assert tool.main([*common, "--apply"]) == 0
    undo_file = json.loads(capsys.readouterr().out)["undo_file"]
    assert library.files() == ["alice/Posts/Images/1.jpg"]
    assert tool.main(["--undo", undo_file, "--apply"]) == 0
    assert library.files() == ["alice/Posts/Images/abcdef.jpg"]
    with pytest.raises(SystemExit):
        tool.main(["--undo", undo_file, str(library.db)])


def test_it_runs_as_an_ofscraper_tool(tmp_path):
    library = Library(tmp_path)
    library.add("abcdef.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "PYTHONPATH": str(ROOT)}
    env.pop(postgres.URL_KEY, None)
    proc = subprocess.run(
        [sys.executable, "-m", "ofscraper", "rename_to_format", str(library.db), "--config", str(library.config)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["to_rename"] == 1
    assert list(home.iterdir()) == []


def test_text_and_labels_come_from_the_database_where_it_holds_them(tmp_path):
    library = Library(tmp_path)
    library.post(501, text="from the post")
    library.post(502, table="messages", text="from the message")
    post = library.add("a.jpg", post_id=501)
    message = library.add("b.jpg", folder="alice/Messages/Images", post_id=502, area="Messages")
    labelled = library.add("c.jpg", post_id=503)
    with closing(sqlite3.connect(library.db)) as conn, conn:
        conn.execute("INSERT INTO labels (label_id, name, type, post_id, model_id) VALUES (1,'Best','custom',503,?)",
                     (CREATOR,))
    library.post(503)
    library.formats("{model_username}/{label}/", "{text}.{ext}")

    result = library.run()

    assert sorted((r["from"], r["to"]) for r in result["renames"]) == sorted([
        (str(post), str(library.root / "alice/None/from the post.jpg")),
        (str(message), str(library.root / "alice/None/from the message.jpg")),
    ])
    assert result["left"] == [{"file": str(labelled), "why": tool.NEEDS.format("{label}")}]


def test_text_saved_sanitized_is_not_used(tmp_path):
    library = Library(tmp_path)
    library.post(501, text="caption")
    path = library.add("a.jpg", post_id=501)
    library.formats(OLD_DIRS, "{text}.{ext}")
    config = json.loads(library.config.read_text(encoding="utf-8"))
    config["advanced_options"] = {"sanitize_text": True}
    library.config.write_text(json.dumps(config), encoding="utf-8")

    result = library.run()

    assert result["left"] == [{"file": str(path), "why": tool.NEEDS.format("{text}")}]


class CaseFoldingOS:
    """The os module as the tool sees it on a disk that doesn't tell the
    case of letters apart (macOS's default; Windows's too, whose
    os.path.normcase also lowers a path: give normcase=str.lower). Every
    path is looked up on the real disk with each part matched without
    regard to case, and a file keeps the spelling it was given."""

    def __init__(self, normcase=None, fail_unlink=None, fold=str.lower):
        self.path = _FoldingPath(self, normcase)
        self.fail_unlink = fail_unlink
        self.fold = fold

    def __getattr__(self, name):
        return getattr(os, name)

    def real(self, path):
        path = os.path.abspath(path)
        found = Path(path).anchor
        for part in Path(path).parts[1:]:
            here = os.path.join(found, part)
            if not os.path.lexists(here) and os.path.isdir(found):
                here = next((os.path.join(found, name) for name in os.listdir(found)
                             if self.fold(name) == self.fold(part)), here)
            found = here
        return found

    def _spelt(self, path):
        """The real folder of `path`, with its own name spelt as given."""
        return os.path.join(self.real(os.path.dirname(os.path.abspath(path))), os.path.basename(path))

    def lstat(self, path):
        return os.lstat(self.real(path))

    def stat(self, path):
        return os.stat(self.real(path))

    def listdir(self, path):
        return os.listdir(self.real(path))

    def makedirs(self, path, exist_ok=False):
        if not os.path.isdir(self.real(path)):
            os.makedirs(self._spelt(path), exist_ok=exist_ok)

    def rmdir(self, path):
        os.rmdir(self.real(path))

    def unlink(self, path):
        if self.fail_unlink and self.fail_unlink(path):
            raise PermissionError(13, "Permission denied")
        os.unlink(self.real(path))

    def link(self, old, new):
        if os.path.lexists(self.real(new)):
            raise FileExistsError(17, "File exists")
        os.link(self.real(old), self._spelt(new))

    def rename(self, old, new):
        source, there = self.real(old), self.real(new)
        if os.path.lexists(there) and not os.path.samefile(source, there):
            os.unlink(there)
        os.rename(source, self._spelt(new))


class _FoldingPath:
    def __init__(self, fs, normcase):
        self._fs = fs
        if normcase:
            self.normcase = normcase

    def __getattr__(self, name):
        return getattr(os.path, name)

    def lexists(self, path):
        return os.path.lexists(self._fs.real(path))

    def exists(self, path):
        return os.path.exists(self._fs.real(path))

    def isdir(self, path):
        return os.path.isdir(self._fs.real(path))

    def islink(self, path):
        return os.path.islink(self._fs.real(path))

    def samefile(self, first, second):
        return os.path.samefile(self._fs.real(first), self._fs.real(second))


def _entries(folder):
    return sorted(os.listdir(folder))


def _simulate_apfs(monkeypatch, mountpoint):
    monkeypatch.setattr(tool, "os", CaseFoldingOS(fold=lambda part: unicodedata.normalize("NFC", part)))
    monkeypatch.setattr(psutil, "disk_partitions", lambda **_: [
        SimpleNamespace(mountpoint=str(mountpoint), fstype="apfs"),
    ])


@pytest.mark.parametrize("normcase", [None, str.lower], ids=["macos", "windows"])
def test_a_case_only_rename_on_a_disk_that_ignores_case_is_made_and_undone(tmp_path, monkeypatch, normcase):
    library = Library(tmp_path)
    path = library.add("ABCDEF.jpg", link="https://cdn.example/files/x/y/abcdef.jpg?Tag=1")
    rows = library.rows()
    monkeypatch.setattr(tool, "os", CaseFoldingOS(normcase))

    result = library.run(apply=True)

    assert (result["renamed"], result["rows_changed"], result["left"]) == (1, 1, [])
    assert _entries(path.parent) == ["abcdef.jpg"]
    assert library.rows()[0][2] == "abcdef.jpg"
    # run again: the file has its new name
    assert library.run(apply=True)["unchanged"] == 1

    done = tool.undo(result["undo_file"], apply=True)

    assert (done["renamed_back"], done["rows_restored"], done["left"]) == (1, 1, [])
    assert _entries(path.parent) == ["ABCDEF.jpg"]
    assert library.rows() == rows
    again = tool.undo(result["undo_file"], apply=True)
    assert (again["files_to_rename_back"], again["rows_restored"], again["left"]) == (0, 0, [])
    assert _entries(path.parent) == ["ABCDEF.jpg"]


def test_a_case_only_rename_already_made_on_a_disk_that_ignores_case_is_already_there(tmp_path, monkeypatch):
    library = Library(tmp_path)
    path = library.add("ABCDEF.jpg", link="https://cdn.example/files/x/y/abcdef.jpg?Tag=1")
    path.rename(path.with_name("abcdef.jpg"))
    monkeypatch.setattr(tool, "os", CaseFoldingOS())

    result = library.run(apply=True)

    assert (result["already_there"], result["renamed"], result["rows_changed"]) == (1, 0, 1)
    assert _entries(path.parent) == ["abcdef.jpg"]


@pytest.mark.parametrize("owner_uses_nfd", [False, True], ids=["owner-nfc", "owner-nfd"])
@pytest.mark.parametrize("owner_on_disk", [True, False], ids=["present", "missing"])
def test_a_unicode_alias_of_another_rows_file_is_left(tmp_path, monkeypatch, owner_uses_nfd, owner_on_disk):
    library = Library(tmp_path)
    composed = "caf\N{LATIN SMALL LETTER E WITH ACUTE}.jpg"
    decomposed = unicodedata.normalize("NFD", composed)
    recorded_name, target_name = (decomposed, composed) if owner_uses_nfd else (composed, decomposed)
    source = library.add("source.jpg", on_disk=not owner_on_disk, content=b"same size")
    owner = library.add(recorded_name, area="Messages", on_disk=owner_on_disk, content=b"same size")
    library.formats(OLD_DIRS, target_name)
    config = json.loads(library.config.read_text(encoding="utf-8"))
    config["type_options"] = {"messages": {"dir_format": "alice/Posts/Images", "file_format": recorded_name}}
    library.config.write_text(json.dumps(config), encoding="utf-8")
    rows = library.rows()
    _simulate_apfs(monkeypatch, library.root)

    result = library.run(apply=True)

    assert result["already_there"] == result["renamed"] == result["rows_changed"] == 0
    assert result["left"] == [{"file": str(source), "why": tool.RECORDED,
                               "new_place": str(owner.with_name(target_name))}]
    assert (owner if owner_on_disk else source).read_bytes() == b"same size"
    assert not (source if owner_on_disk else owner).exists()
    assert library.rows() == rows


def test_a_missing_unicode_spelling_does_not_reserve_a_distinct_name(tmp_path):
    composed = "caf\N{LATIN SMALL LETTER E WITH ACUTE}.jpg"
    decomposed = unicodedata.normalize("NFD", composed)
    probe = tmp_path / composed
    probe.touch()
    if probe.with_name(decomposed).exists():
        pytest.skip("this filesystem treats Unicode spellings as equivalent")

    library = Library(tmp_path)
    source = library.add("source.jpg")
    owner = library.add(decomposed, downloaded=0, on_disk=False)
    library.formats(OLD_DIRS, composed)
    owner_row = library.rows()[1]

    result = library.run(apply=True)

    assert (result["renamed"], result["rows_changed"], result["left"]) == (1, 1, [])
    assert source.with_name(composed).is_file()
    assert not owner.exists()
    assert library.rows()[1] == owner_row


def test_unicode_aliases_of_a_new_destination_conflict_on_apfs(tmp_path, monkeypatch):
    library = Library(tmp_path)
    composed = "caf\N{LATIN SMALL LETTER E WITH ACUTE}"
    decomposed = unicodedata.normalize("NFD", composed)
    library.post(501, text=composed)
    library.post(502, text=decomposed)
    sources = [library.add("first.jpg", post_id=501), library.add("second.jpg", post_id=502)]
    library.formats("new/subfolder", "{text}.{ext}")
    rows = library.rows()
    _simulate_apfs(monkeypatch, library.root)

    for apply in (False, True):
        result = library.run(apply=apply)
        assert (result["to_rename"], result["renamed"], result["rows_changed"]) == (0, 0, 0)
        assert {entry["why"] for entry in result["left"]} == {tool.SAME_TARGET}
        assert {entry["file"] for entry in result["left"]} == {str(source) for source in sources}
        assert all(source.is_file() for source in sources)
        assert library.rows() == rows


@pytest.mark.skipif(not hasattr(os, "link") or os.name == "nt", reason="hard links where a rename is made with one")
def test_a_link_left_by_a_stopped_case_only_rename_is_finished(tmp_path):
    library = Library(tmp_path)
    path = library.add("ABCDEF.jpg", link="https://cdn.example/files/x/y/abcdef.jpg?Tag=1")
    os.link(path, path.with_name("abcdef.jpg"))

    result = library.run(apply=True)

    assert (result["renamed"], result["left"]) == (1, [])
    assert _entries(path.parent) == ["abcdef.jpg"]
    assert library.rows()[0][2] == "abcdef.jpg"


@pytest.mark.skipif(not hasattr(os, "link") or os.name == "nt", reason="hard links where a rename is made with one")
def test_an_undo_that_stopped_after_its_link_is_finished(tmp_path):
    library = Library(tmp_path)
    path = library.add("abcdef.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    undo_file = library.run(apply=True)["undo_file"]
    os.link(path.with_name("1.jpg"), path)

    done = tool.undo(undo_file, apply=True)

    assert (done["renamed_back"], done["rows_restored"], done["left"]) == (1, 1, [])
    assert library.files() == ["alice/Posts/Images/abcdef.jpg"]


@pytest.mark.parametrize("normcase", [None, str.lower], ids=["macos", "windows"])
def test_rows_that_spell_one_file_differently_on_a_disk_that_ignores_case_are_one_file(
        tmp_path, monkeypatch, normcase):
    library = Library(tmp_path)
    path = library.add("shared.jpg", post_id=501, media_id=5)
    library.add("SHARED.jpg", folder="alice/posts/images", post_id=502, media_id=5, on_disk=False)
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    monkeypatch.setattr(tool, "os", CaseFoldingOS(normcase))

    result = library.run(apply=True)

    assert (result["files"], result["renamed"], result["rows_changed"], result["left"]) == (1, 1, 2, [])
    assert library.files() == ["alice/Posts/Images/5.jpg"]
    assert {row[1:] for row in library.rows()} == {(str(path.parent), "5.jpg")}


def test_the_row_of_another_media_that_records_the_same_file_keeps_its_name(tmp_path):
    """A collision left the file of one media where another one's row
    (downloaded = 0) records its own: that row isn't the renamed file's."""
    library = Library(tmp_path)
    path = library.add("abcdef.jpg")
    library.add("abcdef.jpg", media_id=99, downloaded=0, on_disk=False)
    library.formats(OLD_DIRS, "{media_id}.{ext}")

    result = library.run(apply=True)

    assert (result["renamed"], result["rows_changed"]) == (1, 1)
    assert library.rows() == [(1, str(path.parent), "1.jpg"), (99, str(path.parent), "abcdef.jpg")]


@pytest.mark.parametrize("normcase", [None, str.lower], ids=["macos", "windows"])
def test_a_collided_row_spelt_as_the_new_name_on_a_disk_that_ignores_case_doesnt_stop_the_rename(
        tmp_path, monkeypatch, normcase):
    """The row of another media (downloaded = 0) that records the file
    already spelt as its new name doesn't make the downloaded one's
    differently spelt file and row unchanged."""
    library = Library(tmp_path)
    path = library.add("abcdef.jpg", link="https://cdn.example/files/x/y/ABCDEF.jpg?Tag=1")
    library.add("ABCDEF.jpg", media_id=99, downloaded=0, on_disk=False)
    monkeypatch.setattr(tool, "os", CaseFoldingOS(normcase))

    result = library.run(apply=True)

    assert (result["unchanged"], result["renamed"], result["rows_changed"], result["left"]) == (0, 1, 1, [])
    assert _entries(path.parent) == ["ABCDEF.jpg"]
    assert library.rows() == [(1, str(path.parent), "ABCDEF.jpg"), (99, str(path.parent), "ABCDEF.jpg")]


@pytest.mark.parametrize("normcase", [None, str.lower], ids=["macos", "windows"])
def test_a_file_spelt_otherwise_than_its_row_on_a_disk_that_ignores_case_is_renamed(
        tmp_path, monkeypatch, normcase):
    """A row that already records the new name doesn't make the file
    unchanged while the disk spells its name otherwise."""
    library = Library(tmp_path)
    path = library.add("abcdef.jpg")
    path.rename(path.with_name("ABCDEF.jpg"))
    monkeypatch.setattr(tool, "os", CaseFoldingOS(normcase))

    result = library.run(apply=True)

    assert (result["unchanged"], result["renamed"], result["left"]) == (0, 1, [])
    assert _entries(path.parent) == ["abcdef.jpg"]
    assert library.rows()[0][1:] == (str(path.parent), "abcdef.jpg")
    # run again: nothing is left to do
    assert library.run(apply=True)["unchanged"] == 1


@pytest.mark.parametrize("normcase", [None, str.lower], ids=["macos", "windows"])
def test_a_folder_spelt_as_the_new_name_on_a_disk_that_ignores_case_is_not_the_file(
        tmp_path, monkeypatch, normcase):
    """The file is gone and a folder has its name, spelt as the new name:
    the folder isn't taken for the file, moved, or recorded in a row."""
    library = Library(tmp_path)
    path = library.add("ABCDEF.jpg", link="https://cdn.example/files/x/y/abcdef.jpg?Tag=1", on_disk=False)
    (path.parent / "abcdef.jpg").mkdir(parents=True)
    rows = library.rows()
    monkeypatch.setattr(tool, "os", CaseFoldingOS(normcase))

    result = library.run(apply=True)

    assert (result["already_there"], result["renamed"], result["rows_changed"]) == (0, 0, 0)
    assert [left["why"] for left in result["left"]] == [tool.OLD_NOT_A_FILE]
    assert _entries(path.parent) == ["abcdef.jpg"] and (path.parent / "abcdef.jpg").is_dir()
    assert library.rows() == rows


def test_a_folder_at_the_old_place_is_not_moved(tmp_path):
    library = Library(tmp_path)
    path = library.add("abcdef.jpg", on_disk=False)
    path.mkdir(parents=True)
    rows = library.rows()
    library.formats(OLD_DIRS, "{media_id}.{ext}")

    result = library.run(apply=True)

    assert (result["renamed"], result["rows_changed"]) == (0, 0)
    assert [left["why"] for left in result["left"]] == [tool.OLD_NOT_A_FILE]
    assert _entries(path.parent) == ["abcdef.jpg"] and path.is_dir()
    assert library.rows() == rows


@pytest.mark.parametrize("normcase", [None, str.lower], ids=["macos", "windows"])
def test_rows_spelt_otherwise_than_a_file_that_has_its_new_name_are_changed_and_undone(
        tmp_path, monkeypatch, normcase):
    library = Library(tmp_path)
    path = library.add("ABCDEF.jpg", link="https://cdn.example/files/x/y/abcdef.jpg?Tag=1")
    path.rename(path.with_name("abcdef.jpg"))
    rows = library.rows()
    monkeypatch.setattr(tool, "os", CaseFoldingOS(normcase))

    result = library.run(apply=True)

    assert (result["unchanged"], result["already_there"], result["renamed"], result["rows_changed"],
            result["left"]) == (0, 1, 0, 1, [])
    assert _entries(path.parent) == ["abcdef.jpg"]
    assert library.rows()[0][2] == "abcdef.jpg"

    done = tool.undo(result["undo_file"], apply=True)

    assert (done["renamed_back"], done["rows_restored"], done["left"]) == (0, 1, [])
    assert _entries(path.parent) == ["abcdef.jpg"]
    assert library.rows() == rows


def test_a_folder_at_the_new_place_is_not_taken_for_the_file(tmp_path):
    library = Library(tmp_path)
    path = library.add("abcdef.jpg", on_disk=False)
    with closing(sqlite3.connect(library.db)) as conn, conn:
        conn.execute("UPDATE medias SET size = NULL")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    path.with_name("1.jpg").mkdir(parents=True)

    result = library.run(apply=True)

    assert result["already_there"] == 0
    assert result["left"] == [{"file": str(path), "why": tool.NOT_A_FILE, "new_place": str(path.with_name("1.jpg"))}]
    assert library.rows()[0][2] == "abcdef.jpg"


def test_no_undo_file_is_kept_when_nothing_was_changed(tmp_path, monkeypatch):
    library = Library(tmp_path)
    path = library.add("abcdef.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")

    def fails(old, new):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(tool, "rename_file", fails)
    result = library.run(apply=True)

    assert (result["renamed"], result["rows_changed"], result["undo_file"]) == (0, 0, None)
    assert list(library.db.parent.glob("*.json")) == []
    assert path.is_file()


@pytest.mark.skipif(not hasattr(os, "link") or os.name == "nt", reason="hard links where a rename is made with one")
def test_a_rename_whose_old_name_cant_be_removed_leaves_no_copy(tmp_path, monkeypatch):
    library = Library(tmp_path)
    path = library.add("abcdef.jpg")
    library.formats(OLD_DIRS, "{media_id}.{ext}")
    fs = CaseFoldingOS(fail_unlink=lambda p: p == str(path))
    fs.real = staticmethod(os.path.abspath)  # a disk that tells case apart
    monkeypatch.setattr(tool, "os", fs)

    result = library.run(apply=True)

    assert result["renamed"] == 0 and "could not be renamed" in result["left"][0]["why"]
    assert library.files() == ["alice/Posts/Images/abcdef.jpg"]
    assert library.rows()[0][2] == "abcdef.jpg"


def test_a_config_with_unescaped_backslashes_is_refused_as_a_run_refuses_it(tmp_path):
    """The scraper's config_context reads config.json with json.loads and
    asks to fix one it can't read; this refuses the same file, without
    asking (config_file.json_loads, which would read it, only reads a
    config.json that config_context has passed)."""
    library = Library(tmp_path)
    library.add("abcdef.jpg")
    # written by hand on Windows: a backslash that isn't escaped
    library.config.write_text(
        '{"file_options": {"save_location": "%s", "dir_format": "{model_username}\\All",'
        ' "file_format": "{media_id}.{ext}"}}' % library.root.as_posix(), encoding="utf-8")

    with pytest.raises(ValueError, match="Run the scraper once to fix it"):
        library.run()


class _WindowsFolders:
    """os for _remove_emptied as on Windows: ntpath, and a record of rmdir."""

    def __init__(self):
        import ntpath

        self.path = ntpath
        self.removed = []

    def rmdir(self, folder):
        self.removed.append(folder)


def test_old_folders_on_another_drive_than_the_save_location_stay(monkeypatch):
    fs = _WindowsFolders()
    monkeypatch.setattr(tool, "os", fs)

    assert tool._remove_emptied([r"D:\media\alice\Posts\a.jpg"], r"C:\media") == []
    assert fs.removed == []


def test_old_folders_spelt_in_another_case_than_the_save_location_are_removed(monkeypatch):
    fs = _WindowsFolders()
    monkeypatch.setattr(tool, "os", fs)

    removed = tool._remove_emptied([r"C:\Media\alice\Posts\a.jpg"], r"c:\media")

    assert removed == fs.removed == [r"C:\Media\alice\Posts", r"C:\Media\alice"]

def test_emptied_folders_are_removed_under_a_type_options_root(tmp_path):
    # a file moved out of a type_options save_location leaves its folders
    # empty there, outside the main save location
    old = tmp_path / "videos" / "alice" / "Posts" / "a.mp4"
    old.parent.mkdir(parents=True)
    removed = tool._remove_emptied([str(old)], str(tmp_path / "downloads"), str(tmp_path / "videos"))
    assert removed == [str(old.parent), str(old.parent.parent)]
    assert (tmp_path / "videos").is_dir()


def test_a_row_without_a_media_type_is_left_when_a_media_type_entry_is_set(tmp_path):
    # which root the file belongs under depends on its media type
    library = Library(tmp_path)
    library.post(501)
    path = library.add("abcdef.jpg", post_id=501, kind=None)
    config = json.loads(library.config.read_text(encoding="utf-8"))
    config["type_options"] = {"videos": {"save_location": str(tmp_path / "videos")}}
    library.config.write_text(json.dumps(config), encoding="utf-8")

    result = library.run()

    assert result["to_rename"] == 0
    assert result["left"] == [{"file": str(path), "why": tool.NEEDS.format("{mediatype}")}]
    assert result["type_options"] == config["type_options"]


@pytest.mark.parametrize("area", ["messages", "Inbox", "unknown"])
def test_a_row_without_an_area_is_left_when_an_area_entry_is_set(tmp_path, area):
    # a download would put the file under the entry's folder; which area
    # it's from isn't recorded
    library = Library(tmp_path)
    library.post(501)
    path = library.add("abcdef.jpg", post_id=501, area=None, media_id=42)
    library.formats("renamed", "{media_id}.{ext}")
    config = json.loads(library.config.read_text(encoding="utf-8"))
    config["responsetype"] = {"message": "Inbox"}
    config["type_options"] = {area: {"dir_format": "special"}}
    library.config.write_text(json.dumps(config), encoding="utf-8")

    result = library.run(apply=True)

    assert result["renamed"] == 0
    assert result["left"] == [{"file": str(path), "why": tool.NEEDS.format("{response_type}")}]
    assert path.is_file()


def test_an_unknown_type_entry_does_not_block_a_rename_without_an_area(tmp_path):
    library = Library(tmp_path)
    library.post(501)
    library.add("abcdef.jpg", post_id=501, area=None, media_id=42)
    library.formats("renamed", "{media_id}.{ext}")
    config = json.loads(library.config.read_text(encoding="utf-8"))
    config["type_options"] = {"mesages": {"dir_format": "other"}}
    library.config.write_text(json.dumps(config), encoding="utf-8")

    result = library.run(apply=True)

    assert result["renamed"] == 1
    assert result["left"] == []
    assert library.files() == ["renamed/42.jpg"]


def test_a_save_root_inside_another_is_never_removed(tmp_path):
    outer, inner = tmp_path / "data", tmp_path / "data" / "of"
    old = inner / "alice" / "Posts" / "a.jpg"
    old.parent.mkdir(parents=True)
    removed = tool._remove_emptied([str(old)], str(inner), str(outer))
    assert removed == [str(old.parent), str(old.parent.parent)]
    assert inner.is_dir()


def test_the_path_key_reads_a_folder_once_for_many_decomposed_names(tmp_path, monkeypatch):
    """A folder of NFD-spelt names (from a Mac) was listed again for each one,
    once per name while the plan was made"""
    folder = tmp_path / "a_creator"
    folder.mkdir()
    names = [unicodedata.normalize("NFD", f"caf\u00e9_{n}.jpg") for n in range(20)]
    listed = []
    real = os.listdir
    monkeypatch.setattr(tool.os, "listdir", lambda path=".": listed.append(str(path)) or real(path))
    # each NFD name finds the same file as its NFC spelling, as on APFS
    monkeypatch.setattr(tool, "_same_file", lambda a, b: True)

    key = tool._path_key()
    for name in names:
        key(str(folder / name))

    assert listed.count(os.path.normcase(str(folder))) <= 1
