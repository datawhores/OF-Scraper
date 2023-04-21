import tempfile
from src.db.operations import *
import pytest
from test_constants import *
from src.api.posts import Post,Media

def test_message_create(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("src.utils.paths.databasePathHelper",return_value=p.name)
            create_message_table("11111","test")
        except:
            raise Exception



def test_message_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("src.utils.paths.databasePathHelper",return_value=p.name)
            create_message_table("11111")


def test_message_insert(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("src.utils.paths.databasePathHelper",return_value=p.name)
            create_message_table("11111","test")
            write_messages_table(Post(MESSAGES_DICT,"11111","test"))
        except Exception as E:
            print(E)
            raise Exception
def test_message_insert_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("src.utils.paths.databasePathHelper",return_value=p.name)
            create_message_table("11111","test")
            write_messages_table(Post(MESSAGES_DICT,"111","test2"))

def test_message_response(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("src.utils.paths.messageResponsePathHelper",return_value=p.name)
            save_messages_response(MESSAGES_DICT,"11111","test")
        except Exception as E:
            print(E)
            raise Exception
def test_message_response_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("src.utils.paths.messageResponsePathHelpe",return_value=p.name)
            save_messages_response(None,"11111","test")


def test_read_mesage_response(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("src.utils.paths.messageResponsePathHelper",return_value=p.name)
            save_messages_response(MESSAGES_DICT,"11111","test")
            read_messages_response("11111","test")
        except Exception as E:
            print(E)
            raise Exception
def test_read_message_response_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("src.utils.paths.messageResponsePathHelpe",return_value=p.name)
            save_messages_response(MESSAGES_DICT,"11111","test")
            read_messages_response("11112","test")