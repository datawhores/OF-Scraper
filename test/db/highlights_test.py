import tempfile
from src.db.operations import *
import pytest
from test_constants import *
from src.api.posts import Post,Media

def test_highlight_create(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("src.utils.paths.databasePathHelper",return_value=p.name)
            create_stories_table("11111","test")
        except:
            raise Exception



def test_highlight_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("src.utils.paths.databasePathHelper",return_value=p.name)
            create_stories_table("11111")


def test_highlight_insert(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("src.utils.paths.databasePathHelper",return_value=p.name)
            create_stories_table("11111","test")
            write_stories_table(Post(HIGHLIGHT_EXAMPLE,"11111","test"),"11111","test")
        except Exception as E:
            print(E)
            raise Exception
def test_highlight_insert_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("src.utils.paths.databasePathHelper",return_value=p.name)
            create_stories_table("11111","test")
            write_stories_table(Post(HIGHLIGHT_EXAMPLE,"111","test2"))
