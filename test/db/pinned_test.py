import tempfile
from ofscraper.db.operations import *
import pytest
from test.test_constants import *
from ofscraper.api.posts import Post,Media

def test_pinned_create(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("ofscraper.utils.paths.databasePathHelper",return_value=p.name)
            create_post_table("11111","test")
        except:
            raise Exception



def test_pinned_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("ofscraper.utils.paths.databasePathHelper",return_value=p.name)
            create_post_table("11111")


def test_pinned_insert(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("ofscraper.utils.paths.databasePathHelper",return_value=p.name)
            create_post_table("11111","test")
            write_post_table(Post(PINNED_POSTS_EXAMPLE,"11111","test"),"11111","test")
        except Exception as E:
            print(E)
            raise Exception
def test_pinned_insert_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("ofscraper.utils.paths.databasePathHelper",return_value=p.name)
            create_post_table("11111","test")
            write_post_table(Post(PINNED_POSTS_EXAMPLE,"111","test2"))

