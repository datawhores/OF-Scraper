import tempfile
import traceback

from ofscraper.classes.posts import Post
from ofscraper.const.test_constants import *
from ofscraper.db.operations import *


def test_media_create(mocker):
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
            create_post_table("11111", "test")
            write_post_table(Post(TIMELINE_EXAMPLE, "11111", "test"), "11111", "test")
            create_media_table(model_id="11111", username="test")
        except:
            raise Exception


# def test_media_failure(mocker):
#     with tempfile.NamedTemporaryFile() as p:
#         with pytest.raises(Exception):
#             mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathHelper",return_value=pathlib.Path(p.name))
#             create_media_table("11111")


def test_media_insert(mocker):
    with tempfile.NamedTemporaryFile() as p:
        with tempfile.NamedTemporaryFile() as d:
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
                mocker.patch(
                    "ofscraper.db.operations.FileLock.acquire", return_value=True
                )
                mocker.patch(
                    "ofscraper.db.operations.FileLock.release", return_value=True
                )
                create_media_table(11111, "test")
                update_media_table_download(
                    Post(TIMELINE_EXAMPLE, model_id="11111", username="test").media[0],
                    d.name,
                    model_id="11111",
                    username="test",
                )
            except Exception as E:
                print(E, traceback.format_exc())
                raise Exception


# def test_media_insert_failure(mocker):
#     with tempfile.NamedTemporaryFile() as p:
#         with tempfile.NamedTemporaryFile() as d:
#             with pytest.raises(Exception):
#                 a=mocker
#                 a.trace=None
#                 mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathHelper",return_value=pathlib.Path(p.name))
#                 mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathCopyHelper",return_value=pathlib.Path(p.name))
#                 mocker.patch("ofscraper.db.operations.log",new_callabe=a)
#                 create_media_table(11111,"test")
#                 update_media_table_download(Post(TIMELINE_EXAMPLE,"11111","test3").media[0],d.name,"11111","test32")
