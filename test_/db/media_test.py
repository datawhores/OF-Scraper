import tempfile
from ofscraper.db.operations import *
import pytest
from  test_.test_constants import *
from ofscraper.classes.posts import Post
from ofscraper.classes.media import Media
from pathlib import Path
from unittest.mock import patch
import traceback
from ofscraper.db.operations import pathlib as operationspath
def test_media_create(mocker):
    with tempfile.NamedTemporaryFile() as p:
        try:
            a=mocker
            a.trace=None
            mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathHelper",return_value=pathlib.Path(p.name))
            mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathCopyHelper",return_value=pathlib.Path(p.name))
            mocker.patch("ofscraper.db.operations.log",new_callabe=a)  

            create_post_table("11111","test")         
            write_post_table(Post(TIMELINE_EXAMPLE,"11111","test"),"11111","test")            
            create_media_table(model_id="11111",username="test")
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
                a=mocker
                a.trace=None
                mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathHelper",return_value=pathlib.Path(p.name))
                mocker.patch("ofscraper.classes.placeholder.Placeholders.databasePathCopyHelper",return_value=pathlib.Path(p.name))
                mocker.patch("ofscraper.db.operations.log",new_callabe=a)                  
                create_media_table(11111,"test")
                update_media_table(Post(TIMELINE_EXAMPLE,model_id="11111",username="test").media[0],d.name,model_id="11111",username="test")
            except Exception as E:
                print(E,traceback.format_exc())
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
#                 update_media_table(Post(TIMELINE_EXAMPLE,"11111","test3").media[0],d.name,"11111","test32")