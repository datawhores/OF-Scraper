import tempfile
from ofscraper.db.operations import *
import pytest
from test.test_constants import *
from ofscraper.classes.posts import Post
from ofscraper.classes.media import Media
from pathlib import Path
from unittest.mock import patch
import traceback
from ofscraper.db.operations import pathlib as operationspath
def test_media_create(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            mocker.patch("ofscraper.db.operations.databasePathHelper",return_value=pathlib.Path(p.name))
            create_media_table("11111","test")
        except:
            raise Exception



def test_media_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:   
        with pytest.raises(Exception):
            mocker.patch("ofscraper.db.operations.databasePathHelper",return_value=pathlib.Path(p.name))
            create_media_table("11111")


def test_media_insert(mocker):
   
   
    with tempfile.NamedTemporaryFile() as p:
        with tempfile.NamedTemporaryFile() as d:
            try:
                mocker.patch("ofscraper.db.operations.databasePathHelper",return_value=pathlib.Path(p.name))
                create_media_table(11111,"test")
                write_media_table(Post(TIMELINE_EXAMPLE,"11111","test").media[0],d.name,"11111","test")
            except Exception as E:
                print(E,traceback.format_exc())
                raise Exception
def test_media_insert_failure(mocker):
    with tempfile.NamedTemporaryFile() as p:
        with tempfile.NamedTemporaryFile() as d:
            with pytest.raises(Exception):
                mocker.patch("ofscraper.utils.paths.databasePathHelper",return_value=p.name)
                create_media_table(11111,"test")
                write_media_table(Post(TIMELINE_EXAMPLE,"11111","test3").media[0],d.name,"11111","test32")