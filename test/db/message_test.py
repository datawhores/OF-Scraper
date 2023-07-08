import tempfile
from ofscraper.db.operations import *
import pytest
from test.test_constants import *
from ofscraper.classes.posts import Post
from ofscraper.classes.media import Media

def test_message_create(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathHelper",return_value=pathlib.Path(p.name))

            create_message_table("11111","test")
        except:
            raise Exception



def test_message_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathHelper",return_value=p.name)
            create_message_table("11111")


def test_message_insert(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathHelper",return_value=pathlib.Path(p.name))
            create_message_table("11111","test")
            write_messages_table(Post(MESSAGES_DICT,"11111","test"))
        except Exception as E:
            print(E)
            raise Exception
def test_message_insert_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathHelper",return_value=p.name)
            create_message_table("11111","test")
            write_messages_table(Post(MESSAGES_DICT,"111","test2"))
