import tempfile

from ofscraper.classes.posts import Post
from ofscraper.const.test_constants import *
from ofscraper.db.operations import *


def test_message_create(mocker):
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
            create_message_table("11111", "test")
        except:
            raise Exception


# def test_message_failure(mocker):
#     with tempfile.NamedTemporaryFile() as p:
#         with pytest.raises(Exception):
#             a=mocker
#             a.trace=None
#             mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathHelper",return_value=pathlib.Path(p.name))
#             mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathCopyHelper",return_value=pathlib.Path(p.name))
#             mocker.patch("ofscraper.db.operations.log",new_callabe=a)
#             create_message_table("11111")


def test_message_insert(mocker):
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
            create_message_table("11111", "test")
            write_messages_table(Post(MESSAGES_DICT, "11111", "test"))
        except Exception as E:
            print(E)
            raise Exception


# def test_message_insert_failure(mocker):
#     with tempfile.NamedTemporaryFile() as p:
#         with pytest.raises(Exception):
#             a=mocker
#             a.trace=None
#             mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathHelper",return_value=pathlib.Path(p.name))
#             mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathCopyHelper",return_value=pathlib.Path(p.name))
#             mocker.patch("ofscraper.db.operations.log",new_callabe=a)

#             create_message_table("11111","test")
#             write_messages_table(Post(MESSAGES_DICT,"111","test2"))
