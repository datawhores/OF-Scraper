import tempfile

from ofscraper.const.test_constants import *
from ofscraper.db.operations import *
from ofscraper.utils.paths.paths import cleanDB


def test_profile_create(mocker):
    cleanDB()
    with tempfile.NamedTemporaryFile() as p:
        try:
            a = mocker
            a.trace = None
            mocker.patch(
                "ofscraper.classes.placeholder.Placeholders.databasePathHelper",
                return_value=pathlib.Path(p.name),
            )
            mocker.patch(
                "ofscraper.classes.placeholder.Placeholders.databasePathCopyHelper",
                return_value=pathlib.Path(p.name),
            )
            mocker.patch("ofscraper.db.operations.log", new_callabe=a)
            mocker.patch("ofscraper.db.operations.FileLock.acquire", return_value=True)
            mocker.patch("ofscraper.db.operations.FileLock.release", return_value=True)
            create_profile_table(model_id="11111", username="test")
        except Exception:
            raise Exception


# def test_profile_failure(mocker):
#     with tempfile.NamedTemporaryFile() as p:
#         with pytest.raises(Exception):
#             a=mocker
#             a.trace=None
#             mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathHelper",return_value=pathlib.Path(p.name))
#             mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathCopyHelper",return_value=pathlib.Path(p.name))
#             mocker.patch("ofscraper.db.operations.log",new_callabe=a)
#             create_profile_table("11111")


def test_profile_insert(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            a = mocker
            a.trace = None
            mocker.patch(
                "ofscraper.classes.placeholder.Placeholders.databasePathHelper",
                return_value=pathlib.Path(p.name),
            )
            mocker.patch(
                "ofscraper.classes.placeholder.Placeholders.databasePathCopyHelper",
                return_value=pathlib.Path(p.name),
            )
            mocker.patch("ofscraper.db.operations.log", new_callabe=a)
            mocker.patch("ofscraper.db.operations.FileLock.acquire", return_value=True)
            mocker.patch("ofscraper.db.operations.FileLock.release", return_value=True)
            create_profile_table(model_id="11111", username="test")
            write_profile_table(model_id="11111", username="test")
        except Exception as E:
            print(E)
            raise Exception


# def test_profile_insert_failure(mocker):
#     with tempfile.NamedTemporaryFile() as p:
#         with pytest.raises(Exception):
#             a=mocker
#             a.trace=None
#             mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathHelper",return_value=pathlib.Path(p.name))
#             mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathCopyHelper",return_value=pathlib.Path(p.name))
#             mocker.patch("ofscraper.db.operations.log",new_callabe=a)
#             create_profile_table()
#             write_profile_table("11112","test")
