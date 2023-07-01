import tempfile
from ofscraper.db.operations import *
import pytest
from test.test_constants import *
from ofscraper.api.posts import Post,Media

def test_post_create(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("ofscraper.db.operations.databasePathHelper",return_value=pathlib.Path(p.name))
            create_post_table("11111","test")
        except:
            raise Exception



def test_post_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("ofscraper.utils.paths.databasePathHelper",return_value=p.name)
            create_post_table("11111")


def test_post_insert(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("ofscraper.db.operations.databasePathHelper",return_value=pathlib.Path(p.name))
            create_post_table("11111","test")
            write_post_table(Post(TIMELINE_EXAMPLE,"11111","test"),"11111","test")
        except Exception as E:
            print(E)
            raise Exception
def test_post_insert_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("ofscraper.utils.paths.databasePathHelper",return_value=p.name)
            create_post_table("11111","test")
            write_post_table(Post(TIMELINE_EXAMPLE,"111","test2"))
