import tempfile
from src.db.operations import *
import pytest
from test_constants import *
from src.api.posts import Post,Media

def test_post_create(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("src.utils.paths.databasePathHelper",return_value=p.name)
            create_post_table("11111","test")
        except:
            raise Exception



def test_post_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("src.utils.paths.databasePathHelper",return_value=p.name)
            create_post_table("11111")


def test_post_insert(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("src.utils.paths.databasePathHelper",return_value=p.name)
            create_post_table("11111","test")
            write_post_table(Post(TIMELINE_EXAMPLE,"11111","test"),"11111","test")
        except Exception as E:
            print(E)
            raise Exception
def test_post_insert_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("src.utils.paths.databasePathHelper",return_value=p.name)
            create_post_table("11111","test")
            write_post_table(Post(TIMELINE_EXAMPLE,"111","test2"))

def test_post_response(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("src.utils.paths.timelineResponsePathHelper",return_value=p.name)
            save_timeline_response(TIMELINE_EXAMPLE,"11111","test")
        except Exception as E:
            print(E)
            raise Exception
def test_post_response_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("src.utils.paths.timelineResponsePathHelper",return_value=p.name)
            save_timeline_response("11111",None)


def test_read_post_response(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("src.utils.paths.timelineResponsePathHelper",return_value=p.name)
            save_timeline_response(TIMELINE_EXAMPLE,"11111","test")
            read_timeline_response("11111","test")
        except Exception as E:
            print(E)
            raise Exception
def test_read_post_response_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("src.utils.paths.postResponsePathHelpe",return_value=p.name)
            save_timeline_response(TIMELINE_EXAMPLE,"11111","test")
            read_timeline_response("11112","test")