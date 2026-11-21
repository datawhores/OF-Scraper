"""move_creator_files (#644) on a user_data.db. Every file it moves is a
small one made here, under pytest's tmp_path."""

import errno
import functools
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

import ofscraper.commands.move_creator_files as tool
import ofscraper.db.postgres as postgres
from ofscraper.db.operations_.media import mediaCreate
from ofscraper.db.operations_.others import schemaCreate, siteInsert
from ofscraper.db.operations_.profile import profilesCreate

ROOT = Path(__file__).resolve().parents[1]
CREATOR = 10
OLD, NEW, FIRST = "old_name", "new_name", "first_name"
# when each name was last seen; none is on a boundary
SEEN = {FIRST: "2023-01-05T08:07:06+00:00", OLD: "2024-03-01T09:30:10+00:00", NEW: "2025-06-11T10:20:30+00:00"}


@pytest.fixture(autouse=True)
def no_url(monkeypatch):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)
    monkeypatch.delenv(tool.PLACEHOLDER_KEY, raising=False)


class Library:
    """A creator's user_data.db, made with the scraper's own tables, and the
    folder their files are in."""

    def __init__(self, tmp_path, names=((OLD, SEEN[OLD]), (NEW, SEEN[NEW])), model_id=CREATOR, site=None, under=""):
        self.model_id = model_id
        self.root = tmp_path / "media"
        self.root.mkdir(exist_ok=True)
        # `under`: a folder of .data for the file (the other site's)
        self.db = tmp_path / ".data" / under / str(model_id) / "user_data.db"
        self.db.parent.mkdir(parents=True)
        self.count = 0
        with closing(sqlite3.connect(self.db)) as conn, conn:
            for create in (mediaCreate, profilesCreate, schemaCreate):
                conn.execute(create)
            if site:
                conn.execute(siteInsert, (site,))
            conn.executemany(
                "INSERT INTO profiles (user_id, username, first_seen_at, last_seen_at) VALUES (?,?,?,?)",
                [(model_id, name, last, last) for name, last in names],
            )

    def add(self, folder, filename="a.jpg", content=None, size=True, on_disk=True, directory=None, model_id=None):
        """A media row that records `filename` in `folder` (under the media
        folder), and the file itself. Returns the file's path."""
        self.count += 1
        path = self.root / folder / filename
        content = f"content of media {self.model_id}-{self.count}".encode() if content is None else content
        if on_disk:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "INSERT INTO medias (media_id, post_id, directory, filename, size, downloaded, hash, model_id)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    self.count, 1000 + self.count, str(path.parent) if directory is None else directory, filename,
                    len(content) if size is True else size, 1, f"hash-{self.count}", model_id or self.model_id,
                ),
            )
        return path

    def rows(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute("SELECT * FROM medias ORDER BY id").fetchall()

    def recorded(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return [
                str(Path(directory, filename))
                for directory, filename in conn.execute("SELECT directory, filename FROM medias ORDER BY id")
            ]

    def everything(self):
        return listing(self.root), self.rows()


def listing(root):
    """Every folder and file under a folder: its bytes, or None for a folder."""
    return {
        path.relative_to(root).as_posix(): (None if path.is_dir() else path.read_bytes())
        for path in sorted(Path(root).rglob("*"))
    }


@pytest.fixture
def library(tmp_path):
    return Library(tmp_path)


@pytest.fixture
def split(library):
    return split_files(library)


def split_files(library):
    """A creator whose files are split over two folders: four under the old
    name, one already under the new one, and a file in the old folder that
    the database knows nothing of."""
    library.add(f"{OLD}/Posts/Images", "a.jpg")
    library.add(f"{OLD}/Posts/Images", "b.jpg")
    library.add(f"{OLD}/Posts/Videos", "c.mp4")
    library.add(f"{OLD}/Messages/Images", "d.jpg")
    library.add(f"{NEW}/Posts/Images", "e.jpg")
    (library.root / OLD / "Posts" / "Images" / "notes.txt").write_bytes(b"another tool's")
    return library


AFTER = ["Posts/Images/a.jpg", "Posts/Images/b.jpg", "Posts/Videos/c.mp4", "Messages/Images/d.jpg", "Posts/Images/e.jpg"]


def under(library, name, *relative):
    return [str(library.root / name / path) for path in relative]


def stop_at(monkeypatch, nth, outcome):
    """The `nth` rename of the run ends in `outcome`; the others are real."""
    real, calls = os.rename, []

    def rename(src, dst):
        calls.append(src)
        if len(calls) == nth:
            raise outcome
        real(src, dst)

    monkeypatch.setattr(os, "rename", rename)


def cli(capsys, *args):
    capsys.readouterr()
    try:
        code = tool.main([str(arg) for arg in args]) or 0
    except SystemExit as stopped:
        code = stopped.code
    said = capsys.readouterr()
    return code, said.out, said.err


# --- preview and apply ---


def test_preview_reports_and_changes_nothing(split):
    before = split.everything()
    images, new = split.root / OLD / "Posts" / "Images", split.root / NEW

    report = tool.on_file(split.db)

    assert split.everything() == before
    assert (report["to"], report["why"]) == (NEW, f"the name seen last ({SEEN[NEW]})")
    assert report["creator"] == {"site": "onlyfans", "model_id": CREATOR}
    assert report["folders"] == [
        {"from": str(split.root / OLD / "Messages" / "Images"), "to": str(new / "Messages" / "Images"), "files": 1},
        {"from": str(images), "to": str(new / "Posts" / "Images"), "files": 2},
        {"from": str(split.root / OLD / "Posts" / "Videos"), "to": str(new / "Posts" / "Videos"), "files": 1},
    ]
    assert [report[count] for count in ("to_move", "already_there", "taken", "not_found")] == [4, 0, 0, 0]
    assert (report["applied"], report["moved"], report["rows_changed"], report["left"]) == (False, 0, 0, [])


def test_apply_moves_the_recorded_files_and_points_their_rows_at_them(split):
    files, rows = split.everything()

    report = tool.on_file(split.db, apply=True)

    assert (report["applied"], report["moved"], report["rows_changed"], report["left"]) == (True, 4, 4, [])
    assert split.recorded() == under(split, NEW, *AFTER)
    assert all((split.root / NEW / path).read_bytes() == files[f"{OLD}/{path}"] for path in AFTER[:4])
    # nothing else of a row changed
    assert [row[:4] + row[5:] for row in split.rows()] == [row[:4] + row[5:] for row in rows]
    # a file the database doesn't record stays, and so does its folder; the
    # folders that were emptied are gone
    assert (split.root / OLD / "Posts" / "Images" / "notes.txt").read_bytes() == b"another tool's"
    assert sorted(report["folders_removed"]) == sorted(
        str(split.root / OLD / path) for path in ("Messages/Images", "Messages", "Posts/Videos")
    )
    assert not (split.root / OLD / "Messages").exists() and not (split.root / OLD / "Posts" / "Videos").exists()
    # a second run finds nothing to do
    after = split.everything()
    again = tool.on_file(split.db, apply=True)
    assert (again["to_move"], again["already_there"], again["rows_changed"], again["left"]) == (0, 0, 0, [])
    assert split.everything() == after


def test_the_new_names_folder_is_merged_into_file_by_file(library, monkeypatch):
    library.add(f"{OLD}/Posts", "a.jpg")
    there = library.add(f"{NEW}/Posts", "b.jpg")
    unknown = library.root / NEW / "Posts" / "c.jpg"
    unknown.write_bytes(b"not in the database")
    real, tried = os.rmdir, []
    monkeypatch.setattr(os, "rmdir", lambda folder: (tried.append(folder), real(folder))[1])

    report = tool.on_file(library.db, apply=True)

    assert (report["moved"], report["left"]) == (1, [])
    assert library.recorded() == under(library, NEW, "Posts/a.jpg", "Posts/b.jpg")
    assert there.read_bytes() == b"content of media 10-2" and unknown.read_bytes() == b"not in the database"
    # the old name's folders were emptied and are gone; nothing above them
    # was tried
    assert tried == report["folders_removed"] == [str(library.root / OLD / "Posts"), str(library.root / OLD)]


@pytest.mark.parametrize("replaces", [False, True])
def test_a_taken_new_place_is_never_overwritten(library, monkeypatch, replaces):
    if replaces:
        # as a rename is everywhere but on Windows: it replaces the file
        monkeypatch.setattr(os, "rename", os.replace)
    old = library.add(f"{OLD}/Posts", "a.jpg")
    library.add(f"{OLD}/Posts", "b.jpg")
    taken = library.root / NEW / "Posts" / "a.jpg"
    taken.parent.mkdir(parents=True)
    taken.write_bytes(b"not in the database")
    before = library.rows()

    for apply in (False, True):
        report = tool.on_file(library.db, apply=apply)

        assert report["left"] == [{"file": str(old), "why": tool.TAKEN}]
        assert (report["to_move"], report["taken"]) == (1, 1)
        assert old.read_bytes() == b"content of media 10-1" and taken.read_bytes() == b"not in the database"
        assert library.rows()[0] == before[0]
    assert library.recorded() == [str(old), str(library.root / NEW / "Posts" / "b.jpg")]


def test_two_files_that_would_get_one_place_the_second_stays(tmp_path):
    library = Library(tmp_path, names=[(FIRST, SEEN[FIRST]), (OLD, SEEN[OLD]), (NEW, SEEN[NEW])])
    first = library.add(f"{FIRST}/Posts", "a.jpg")
    second = library.add(f"{OLD}/Posts", "a.jpg")

    preview = tool.on_file(library.db)
    report = tool.on_file(library.db, apply=True)

    assert preview["left"] == report["left"] == [{"file": str(second), "why": tool.TAKEN}]
    assert (preview["to_move"], report["moved"]) == (1, 1)
    assert not first.exists() and second.read_bytes() == b"content of media 10-2"
    assert (library.root / NEW / "Posts" / "a.jpg").read_bytes() == b"content of media 10-1"
    assert library.recorded() == [str(library.root / NEW / "Posts" / "a.jpg"), str(second)]


def test_a_file_that_cant_be_renamed_stays_and_the_others_go_on(split, monkeypatch):
    # the second file's new place is on another disk
    stop_at(monkeypatch, 2, OSError(errno.EXDEV, "Invalid cross-device link"))
    old = split.root / OLD / "Posts" / "Images" / "a.jpg"

    report = tool.on_file(split.db, apply=True)

    assert report["left"] == [{"file": str(old), "why": "it could not be moved (Invalid cross-device link)"}]
    assert (report["moved"], report["rows_changed"]) == (3, 3)
    assert old.read_bytes() == b"content of media 10-1"
    assert split.recorded() == [str(old)] + under(split, NEW, *AFTER[1:])


def test_a_file_recorded_by_several_rows_is_moved_once_and_every_row_follows(library):
    library.add(f"{OLD}/Posts", "a.jpg")
    library.add(f"{OLD}/Posts", "a.jpg", on_disk=False, size=None)

    report = tool.on_file(library.db, apply=True)

    assert (report["to_move"], report["moved"], report["rows_changed"]) == (1, 1, 2)
    assert library.recorded() == under(library, NEW, "Posts/a.jpg") * 2


# --- a run that stops part way is finished by running it again ---


@pytest.mark.parametrize("stopped", ["Ctrl-C at the third file", "the rows can't be saved"])
def test_a_run_stopped_before_the_rows_are_saved_is_finished_by_running_it_again(split, monkeypatch, capsys, stopped):
    rows = split.rows()
    with monkeypatch.context() as patch:
        if stopped == "the rows can't be saved":
            outcome, moved = sqlite3.OperationalError("disk I/O error"), 4
            patch.setattr(tool._FileRows, "commit", lambda self: (_ for _ in ()).throw(outcome))
        else:
            outcome, moved = KeyboardInterrupt(), 2
            stop_at(patch, 3, outcome)

        with pytest.raises(type(outcome)):
            tool.on_file(split.db, apply=True)

    # files were moved and no row says so
    assert split.rows() == rows
    assert sum(path.startswith(f"{NEW}/") and data is not None for path, data in listing(split.root).items()) == moved + 1
    assert capsys.readouterr().err == tool.AGAIN.format(moved) + "\n"

    report = tool.on_file(split.db, apply=True)

    assert (report["already_there"], report["moved"], report["rows_changed"], report["left"]) == (moved, 4 - moved, 4, [])
    assert split.recorded() == under(split, NEW, *AFTER)
    assert all(Path(path).is_file() for path in split.recorded())


# --- files that aren't where the database says ---


@pytest.mark.parametrize("size, fits", [(True, True), (None, True), (999, False)])
def test_a_file_already_at_the_new_place_only_gets_its_row_changed_if_its_size_fits(library, size, fits):
    old = library.add(f"{OLD}/Posts", "a.jpg", size=size, on_disk=False)
    new = library.root / NEW / "Posts" / "a.jpg"
    new.parent.mkdir(parents=True)
    new.write_bytes(b"content of media 10-1")
    before = library.everything()

    preview = tool.on_file(library.db)
    assert library.everything() == before
    report = tool.on_file(library.db, apply=True)

    assert new.read_bytes() == b"content of media 10-1" and not old.exists()
    if fits:
        assert (preview["already_there"], report["already_there"], report["rows_changed"]) == (1, 1, 1)
        assert library.recorded() == [str(new)] and report["left"] == []
    else:
        assert preview["left"] == report["left"] == [{"file": str(old), "why": tool.OTHER_SIZE, "new_place": str(new)}]
        assert (report["already_there"], report["rows_changed"]) == (0, 0)
        assert library.everything() == before


def test_a_file_at_neither_place_is_listed_and_its_row_is_left(library):
    old = library.add(f"{OLD}/Posts", "a.jpg", on_disk=False)
    before = library.everything()

    report = tool.on_file(library.db, apply=True)

    assert report["left"] == [{"file": str(old), "why": tool.NOT_FOUND}]
    assert (report["not_found"], report["rows_changed"]) == (1, 0)
    assert library.everything() == before


# --- only that creator ---


def test_another_creators_files_and_rows_are_untouched(split, tmp_path):
    other = Library(tmp_path, model_id=20)
    theirs = other.add(f"{OLD}/Posts/Images", "theirs.jpg")
    before = other.db.read_bytes()

    report = tool.on_file(split.db, apply=True)

    assert report["moved"] == 4
    assert other.db.read_bytes() == before and theirs.read_bytes() == b"content of media 20-1"
    assert not (split.root / NEW / "Posts" / "Images" / "theirs.jpg").exists()


@pytest.mark.parametrize("theirs", ["media", "a name"])
def test_a_file_with_more_than_one_creators_rows_is_refused(split, theirs):
    if theirs == "media":
        split.add(f"{OLD}/Posts", "theirs.jpg", model_id=20)
    else:
        # seen last of all: it would be taken for this creator's current name
        with closing(sqlite3.connect(split.db)) as conn, conn:
            conn.execute("INSERT INTO profiles (user_id, username, last_seen_at) VALUES (20, 'theirs', '2026-01-02T03:04:05+00:00')")
    before = split.everything()

    with pytest.raises(ValueError, match="holds the rows of more than one creator"):
        tool.on_file(split.db, apply=True)

    assert split.everything() == before


# --- which name the files go to ---


@pytest.mark.parametrize(
    "names, said",
    [
        ([(OLD, None), (NEW, None)], "has 2 names recorded and none has a date"),
        ([(OLD, SEEN[OLD]), (NEW, SEEN[OLD])], "has 2 names recorded and more than one was seen last at the same moment"),
        ([(OLD, SEEN[OLD]), (NEW, "sometime")], "A date one of this creator's names was last seen at can't be read"),
    ],
)
def test_where_the_current_name_would_be_a_guess_it_asks_for_to(tmp_path, names, said):
    library = split_files(Library(tmp_path, names=names))
    before = library.everything()

    with pytest.raises(ValueError, match=said) as refused:
        tool.on_file(library.db, apply=True)

    assert str(refused.value).endswith(f"Give --to NAME with the name the files should go to (recorded: {NEW}, {OLD})")
    assert library.everything() == before
    # with --to it goes on
    report = tool.on_file(library.db, apply=True, to=NEW.upper())
    assert (report["to"], report["why"], report["moved"]) == (NEW, "given with --to", 4)


def test_to_must_be_a_recorded_name(split):
    before = split.everything()

    with pytest.raises(ValueError, match=f"--to: someone is not one of the names .* creator \\({NEW}, {OLD}\\)"):
        tool.on_file(split.db, apply=True, to="someone")

    assert split.everything() == before


def test_the_placeholder_of_a_deleted_account_is_only_chosen_with_to(tmp_path, monkeypatch):
    # the placeholder was "seen" last, and is still not where the files go
    names = [(OLD, SEEN[OLD]), ("modeldeleted_10", SEEN[NEW])]
    library = Library(tmp_path, names=names)
    library.add("modeldeleted_10/Posts", "a.jpg")

    assert tool.on_file(library.db)["to"] == OLD
    assert tool.on_file(library.db, to="modeldeleted_10")["to"] == "modeldeleted_10"
    monkeypatch.setenv(tool.PLACEHOLDER_KEY, "Gone")
    other = Library(tmp_path, names=[(OLD, SEEN[OLD]), ("gone", SEEN[NEW])], model_id=30)
    assert tool.on_file(other.db)["to"] == OLD


def test_to_the_old_name_moves_everything_back_under_it(split):
    files, _rows = split.everything()
    tool.on_file(split.db, apply=True)

    report = tool.on_file(split.db, apply=True, to=OLD)

    # also the file that was under the new name before: it is the way back,
    # not an exact undo
    assert (report["to"], report["moved"], report["rows_changed"], report["left"]) == (OLD, 5, 5, [])
    assert split.recorded() == under(split, OLD, *AFTER)
    after = listing(split.root)
    assert {path: data for path, data in after.items() if data is not None} == {
        path.replace(f"{NEW}/", f"{OLD}/"): data for path, data in files.items() if data is not None
    }
    assert not (split.root / NEW).exists()


# --- which part of a path is the name ---


def test_a_library_laid_out_by_id_has_nothing_to_move(library):
    library.add("10/Posts", "a.jpg")
    library.add(f"{OLD} - videos/Posts", "b.jpg")
    library.add(f"x_{OLD}/Posts", "c.jpg")
    library.add(f"{OLD.upper()}/Posts", "d.jpg")
    before = library.everything()

    report = tool.on_file(library.db, apply=True)

    assert (report["to_move"], report["already_there"], report["folders"], report["left"]) == (0, 0, [], [])
    assert library.everything() == before


def test_a_name_that_is_also_another_folder_of_the_path_is_told_apart_by_its_letters(tmp_path):
    library = Library(tmp_path, names=[("Posts", SEEN[OLD]), (NEW, SEEN[NEW])])
    library.add("posts/Posts/Images", "a.jpg")

    report = tool.on_file(library.db, apply=True)

    assert (report["moved"], report["left"]) == (1, [])
    assert library.recorded() == [str(library.root / NEW / "Posts" / "Images" / "a.jpg")]


def test_a_folder_above_the_library_with_an_old_name_is_left_and_listed(library):
    # a library laid out by id, and one by name and id, under a folder that
    # only has the old name (a user's own folder, say)
    by_id = library.add(f"{OLD}/OF/{CREATOR}/Posts", "a.jpg")
    by_both = library.add(f"{OLD}/OF/{OLD}_{CREATOR}/Posts", "b.jpg")
    before = library.everything()

    for apply in (False, True):
        report = tool.on_file(library.db, apply=apply)

        assert report["left"] == [{"file": str(path), "why": tool.LEFT["layout"]} for path in (by_id, by_both)]
        assert (report["to_move"], report["rows_changed"], report["folders_removed"]) == (0, 0, [])
        assert library.everything() == before


@pytest.mark.parametrize("to, moves", [(NEW, False), ("other_name", True)])
def test_a_first_letter_folder_above_the_name_is_left_when_the_letter_would_change(tmp_path, to, moves):
    library = Library(tmp_path, names=[(OLD, SEEN[OLD]), (to, SEEN[NEW])])
    old = library.add(f"OF/{OLD[0].upper()}/{OLD}/Posts", "a.jpg")
    before = library.everything()

    report = tool.on_file(library.db, apply=True)

    if moves:
        assert (report["moved"], report["left"]) == (1, [])
        assert library.recorded() == [str(library.root / "OF" / "O" / to / "Posts" / "a.jpg")]
    else:
        assert report["left"] == [{"file": str(old), "why": tool.LEFT["letter"]}]
        assert library.everything() == before


def test_a_missing_file_isnt_pointed_at_a_file_this_run_moved_for_another_row(tmp_path):
    library = Library(tmp_path, names=[(FIRST, SEEN[FIRST]), (OLD, SEEN[OLD]), (NEW, SEEN[NEW])])
    library.add(f"{FIRST}/Posts", "x.jpg")
    missing = library.add(f"{OLD}/Posts", "x.jpg", on_disk=False, size=None)

    preview = tool.on_file(library.db)
    report = tool.on_file(library.db, apply=True)

    assert preview["left"] == report["left"] == [{"file": str(missing), "why": tool.NOT_FOUND}]
    assert (report["moved"], report["already_there"], report["rows_changed"]) == (1, 0, 1)
    assert library.recorded() == [str(library.root / NEW / "Posts" / "x.jpg"), str(missing)]


def test_a_path_with_two_of_the_creators_names_is_left_and_listed(library):
    old = library.add(f"{OLD}/{NEW}/Posts", "a.jpg")
    before = library.everything()

    report = tool.on_file(library.db, apply=True)

    assert report["left"] == [{"file": str(old), "why": tool.TWICE}]
    assert library.everything() == before


def test_relative_recorded_paths_need_path_root_and_stay_relative(library, tmp_path):
    old = library.add(f"{OLD}/Posts", "a.jpg", directory=f"media/{OLD}/Posts")
    before = library.everything()

    with pytest.raises(ValueError, match="Relative recorded paths require --path-root"):
        tool.on_file(library.db, apply=True)
    assert library.everything() == before

    report = tool.on_file(library.db, apply=True, path_root=tmp_path)

    assert report["moved"] == 1 and not old.exists()
    assert (library.root / NEW / "Posts" / "a.jpg").read_bytes() == b"content of media 10-1"
    assert [row[4] for row in library.rows()] == [f"media/{NEW}/Posts"]


def test_a_full_path_of_another_system_that_names_the_creator_is_refused(library):
    elsewhere = "/srv/media" if os.name == "nt" else "C:\\media"
    separator = "/" if os.name == "nt" else "\\"
    library.add("unused", "a.jpg", directory=f"{elsewhere}{separator}{OLD}{separator}Posts", on_disk=False)
    before = library.everything()

    with pytest.raises(ValueError, match="is a full path on another system"):
        tool.on_file(library.db, apply=True, path_root=library.root)

    assert library.everything() == before


def test_a_fansly_file_is_moved_the_same_way(tmp_path):
    library = split_files(Library(tmp_path, site="fansly", under="Fansly"))

    report = tool.on_file(library.db, apply=True)

    assert report["creator"] == {"site": "fansly", "model_id": CREATOR}
    assert (report["moved"], report["rows_changed"]) == (4, 4)
    assert library.recorded() == under(library, NEW, *AFTER)


# --- the scraper, and the command line ---


def test_a_file_the_scraper_is_writing_to_stops_the_run_before_a_file_is_moved(split, monkeypatch):
    monkeypatch.setattr(tool.sqlite3, "connect", functools.partial(sqlite3.connect, timeout=0.05))
    before = split.everything()
    with closing(sqlite3.connect(split.db)) as scraper:
        scraper.execute("BEGIN IMMEDIATE")

        with pytest.raises(sqlite3.OperationalError, match="database is locked"):
            tool.on_file(split.db, apply=True)
        # a preview only reads
        assert tool.on_file(split.db)["to_move"] == 4

    assert split.everything() == before


def test_cli_previews_by_default_and_says_what_went_wrong_in_one_sentence(split, capsys, monkeypatch):
    before = split.everything()

    code, out, err = cli(capsys, split.db)
    assert (code, err) == (0, "") and json.loads(out)["to_move"] == 4
    assert split.everything() == before

    code, out, err = cli(capsys, split.db, "--to", "someone", "--apply")
    assert (code, out) == (1, "") and err.startswith("Move failed: --to: someone is not one of the names")
    assert cli(capsys, split.db, "--creator", OLD)[0] == 2
    assert cli(capsys, "--postgres", "--creator", OLD)[0] == 2
    assert split.everything() == before

    stop_at(monkeypatch, 2, KeyboardInterrupt())
    code, out, err = cli(capsys, split.db, "--apply")
    assert (code, out, err) == (130, "", tool.AGAIN.format(1) + "\nMove stopped.\n")
    monkeypatch.undo()

    monkeypatch.setenv(postgres.URL_KEY, "postgresql://db.example/library")
    code, out, err = cli(capsys, split.db, "--apply")
    assert code == 0 and err == f"warning: {tool.FILES_NOTICE}\n" and "move_creator_files works" in err
    assert (json.loads(out)["already_there"], json.loads(out)["moved"]) == (1, 3)
    assert split.recorded() == under(split, NEW, *AFTER)


def test_the_command_doesnt_load_the_scraper_or_the_driver(split):
    result = subprocess.run(
        [
            sys.executable, "-c",
            "import sys\n"
            "import ofscraper.commands.move_creator_files as tool\n"
            f"tool.main([{str(split.db)!r}, '--apply'])\n"
            "print(sorted(name for name in sys.modules if name.split('.')[0]"
            " in ('rich', 'dotenv', 'aiohttp', 'psycopg', 'psycopg_pool', 'arrow')"
            " or name.startswith(('ofscraper.utils.settings', 'ofscraper.utils.console',"
            " 'ofscraper.utils.config'))))\n",
        ],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, cwd=ROOT,
        # a setting the scraper would stop on doesn't stop it
        env={**os.environ, "PYTHONPATH": str(ROOT), "OFSC_DOWNLOAD_SEM_DEFAULT": "many"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.rstrip().endswith("\n[]") and json.loads(result.stdout.rsplit("\n", 2)[0])["moved"] == 4
