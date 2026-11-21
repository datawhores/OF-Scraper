"""scripts/creator_names.py --postgres (#631): everything that needs no server.

The server is a stand-in (postgres_stand_in.py), which needs the driver
installed. test_creator_names_postgres_live.py runs the script against a real
server, in CI.
"""

import csv
import sys

import pytest

import ofscraper.db.postgres as postgres
from test.test_creator_names import APRIL, MARCH, MAY, _account, creator_names

URL = "postgresql://scraper:s3cret-word@db.example:5433/library"
# each creator: (model_id, [(name, first seen, last seen)], media)
ONLYFANS = [
    (1, [("old_name", MARCH, APRIL), ("current_name", MAY, MAY), ("undated_name", None, None)], 2),
    (2, [("only_name", MARCH, MARCH)], 1),
    (7, [("zeta_name", None, None)], 0),
]
FANSLY = [(1, [("fansly_name", MARCH, MARCH), ("fansly_other", APRIL, APRIL)], 3)]


@pytest.fixture(autouse=True)
def no_url(monkeypatch):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)


@pytest.fixture
def server(monkeypatch):
    """The stand-in, holding ONLYFANS and FANSLY."""
    pytest.importorskip("psycopg")
    from test.postgres_stand_in import Server

    server = Server()
    monkeypatch.setattr(postgres, "Reader", server.reader)
    monkeypatch.setattr(postgres, "Writer", server.writer)
    for site, creators in (("onlyfans", ONLYFANS), ("fansly", FANSLY)):
        for model_id, names, media in creators:
            server.insert(site, "models", ["model_id"], [(model_id,)])
            server.insert(
                site, "profiles", ["user_id", "username", "first_seen_at", "last_seen_at"],
                [(model_id, *name) for name in names],
            )
            server.insert(
                site, "medias", ["media_id", "post_id", "model_id"],
                [(i, i, model_id) for i in range(media)],
            )
    yield server
    server.close()


def run(monkeypatch, capsys, *args, url=URL):
    """The script with the address in its environment: (exit code, stdout, stderr)."""
    capsys.readouterr()
    with monkeypatch.context() as patch:
        patch.setenv(postgres.URL_KEY, url)
        code = creator_names.main([str(arg) for arg in args])
    said = capsys.readouterr()
    return code, said.out, said.err


def held(server, site="onlyfans"):
    return server.db.execute(
        f"SELECT user_id, username, first_seen_at, last_seen_at FROM {site}.profiles ORDER BY id"
    ).fetchall()


def everything(server):
    return {site: held(server, site) for site in ("onlyfans", "fansly")}


def test_the_listing_and_csv_are_the_ones_the_same_files_give(server, tmp_path, monkeypatch, capsys):
    data = tmp_path / "data"
    for model_id, names, media in ONLYFANS:
        _account(data, model_id, names, media=media)
    before = everything(server)

    _, from_files, _ = run(monkeypatch, capsys, "--data-dir", data, "--all", "--csv", tmp_path / "f.csv", url="")
    code, out, err = run(monkeypatch, capsys, "--postgres", "--all", "--csv", tmp_path / "p.csv")

    assert code == 0 and err == ""
    assert out == from_files
    assert "folder if deleted: current_name" in out
    with open(tmp_path / "f.csv", encoding="utf-8") as f, open(tmp_path / "p.csv", encoding="utf-8") as p:
        assert list(csv.reader(p)) == list(csv.reader(f))
    # only read
    assert everything(server) == before


def test_find_and_the_site(server, monkeypatch, capsys):
    code, out, _ = run(monkeypatch, capsys, "--postgres", "--find", "OLD_NAME")
    assert code == 0
    assert out == (
        "         1       2 media  old_name (seen 2024-03-01 to 2024-04-01)"
        "   also known as: current_name (seen 2024-05-01), undated_name"
        "   folder if deleted: current_name\n\n1 account(s)\n"
    )

    _, out, _ = run(monkeypatch, capsys, "--postgres", "--site", "fansly")
    assert "fansly_name (seen 2024-03-01)   also known as: fansly_other" in out and "old_name" not in out
    assert out.endswith("1 account(s) with more than one name\n")


def test_add_refuses_a_folder_change_unless_forced(server, monkeypatch, capsys):
    before = everything(server)
    code, _, err = run(monkeypatch, capsys, "--postgres", "--add", 7, "alpha_name")
    assert code == 1 and "pass --force" in err
    assert everything(server) == before

    code, out, _ = run(monkeypatch, capsys, "--postgres", "--add", 7, "alpha_name", "--force")
    assert code == 0 and out == "Added: alpha_name -> 7\n"
    assert held(server)[-1] == (7, "alpha_name", None, None)
    assert run(monkeypatch, capsys, "--postgres", "--find", "zeta_name")[1].splitlines()[0].endswith(
        "folder if deleted: alpha_name"
    )


def test_add_with_a_date_writes_one_row_of_that_site(server, monkeypatch, capsys):
    before = everything(server)
    args = ["--postgres", "--site", "fansly", "--add", 1, "older_name", "--seen", "2024-01-01"]

    code, out, _ = run(monkeypatch, capsys, *args)
    assert code == 0 and out == "Added: older_name -> 1, seen 2024-01-01T00:00:00+00:00\n"
    assert held(server, "fansly") == before["fansly"] + [
        (1, "older_name", "2024-01-01 00:00:00+00", "2024-01-01 00:00:00+00")
    ]
    assert held(server) == before["onlyfans"]

    # a name already recorded gets its dates widened, here past the folder's
    code, _, err = run(monkeypatch, capsys, *args[:-1], "2024-06-01")
    assert code == 1 and "pass --force" in err
    code, out, _ = run(monkeypatch, capsys, *args[:-1], "2024-06-01", "--force")
    assert code == 0 and out.startswith("Already recorded: older_name -> 1")
    assert held(server, "fansly")[-1] == (1, "older_name", "2024-01-01 00:00:00+00", "2024-06-01 00:00:00+00")


def test_add_refuses_a_creator_postgresql_has_not(server, monkeypatch, capsys):
    before = everything(server)
    code, _, err = run(monkeypatch, capsys, "--postgres", "--site", "fansly", "--add", 2, "a_name")
    assert code == 1
    assert err == "PostgreSQL has no creator 2 in its fansly tables\n"
    assert everything(server) == before


@pytest.mark.parametrize(
    "args, url, said",
    [
        (["--postgres", "--data-dir", "."], URL, "give --data-dir or --postgres, not both"),
        (["--site", "fansly"], URL, "--site goes with --postgres"),
        (["--postgres"], "", "--postgres needs OFSC_DATABASE_URL set in the environment"),
    ],
)
def test_options_that_do_not_go_together(monkeypatch, capsys, args, url, said):
    code, out, err = run(monkeypatch, capsys, *args, url=url)
    assert code == 1 and out == ""
    assert err.startswith(said)
    assert "s3cret" not in err


def test_without_the_driver_it_says_how_to_get_it(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "psycopg", None)
    code, out, err = run(monkeypatch, capsys, "--postgres")
    assert code == 1 and out == ""
    assert "the PostgreSQL driver isn't installed" in err and "s3cret" not in err


def test_reading_postgresql_says_nothing_about_the_files(server, monkeypatch, capsys):
    code, _, err = run(monkeypatch, capsys, "--postgres")
    assert code == 0 and err == ""
