import src.utils.download as download
import src.utils.paths as paths
from unittest.mock import patch,MagicMock
import platform
import pathlib
import src.utils.config as config
import os
import tempfile

from test_constants import *
from src.utils.download import createfilename
from src.api.posts import Post
import pytest
from src.utils.dates import convert_local_time
import arrow


def test_windows_trunicate():
    with patch('platform.system', MagicMock(return_value="Windows")):
        assert(platform.system())=="Windows"
        long_path=pathlib.Path(WINDOWS_LONGPATH)
        trunicated=download.trunicate(long_path)
        assert(len(str(trunicated)))<=256
        assert(long_path.parent)==trunicated.parent
        assert(long_path.suffix)==trunicated.suffix



def test_linux_trunicate():
    long_path=pathlib.Path(LINUX_LONGPATH)
    trunicated=download.trunicate(long_path)
    assert(len(trunicated.name.encode('utf8')))<=255
    assert(long_path.parent)==trunicated.parent
    assert(long_path.suffix)==trunicated.suffix

def test_user_data_db(mocker):
   migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_LOCATION_DEFAULT,
        "file_size_limit":FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILE_FORMAT_DEFAULT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }

   mocker.patch('src.utils.paths.config', new=migrationConfig)
   assert(str(paths.databasePathHelper(1111,"test")))=="/root/.config/ofscraper/main_profile/.data/test_1111/user_data.db"


def test_user_data_dc_db_str(mocker):
   migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_LOCATION_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILE_FORMAT_DEFAULT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DC,
        "filter": FILTER_DEFAULT
    }

   mocker.patch('src.utils.paths.config', new=migrationConfig)
   assert(str(paths.databasePathHelper("1111","test")))=="/root/test/metadata/user_data.db"    
   

def test_context_provider(mocker):
    with tempfile.TemporaryDirectory() as p:
        with paths.set_directory(p):
            assert(pathlib.Path(".").absolute())==pathlib.Path(p)

def test_context_provider2(mocker):
    with tempfile.TemporaryDirectory() as p:
        with paths.set_directory(p):
            None
        assert(pathlib.Path(".").absolute())!=pathlib.Path(p)

def test_createfilename(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_LOCATION_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILE_FORMAT_DEFAULT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    mocker.patch('src.utils.download.config', new=migrationConfig)
    username="test"
    model_id=1112
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    print(t.media[0].filename)
    assert(createfilename(t.media[0],username,model_id,"mkv"))==f"{t.media[0].filename}.mkv"

def test_createfilename_allkeys(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_LOCATION_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_VALID_ALL,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }

    mocker.patch('src.utils.download.config', new=migrationConfig)
    username="test"
    model_id=1112
    try:
        t=Post(TIMELINE_EXAMPLE,model_id,username)
        assert(createfilename(t.media[0],username,model_id,"mkv"))
    except:
        raise Exception

def test_createfilename_invalid(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_LOCATION_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_ALLVALIDWTHINVALID,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }

    mocker.patch('src.utils.download.config', new=migrationConfig)
    username="test"
    model_id=1112
    with pytest.raises(Exception):
        t=Post(TIMELINE_EXAMPLE,model_id,username)
        assert(createfilename(t.media[0],username,model_id,"mkv"))

def test_settime():
    with tempfile.NamedTemporaryFile() as p:
        test_date=arrow.get("2021")
        download.set_time(p.name,convert_local_time(test_date))
        assert(arrow.get(os.path.getmtime(p.name)).year)==test_date.year

def test_settime2():
    with tempfile.NamedTemporaryFile() as p:
        test_date=arrow.get("2021")
        download.set_time(p.name,convert_local_time(test_date))
        assert(arrow.get(os.path.getmtime(p.name)).float_timestamp)==test_date.float_timestamp
def test_convert_byte_large():
    size=1*10**12
    assert(download.convert_num_bytes(size))==f"{1*10**(12-9)}.0 GB"



def test_convert_byte_small():
    size=1*10**7
    assert(download.convert_num_bytes(size))==f"{1*10**(7-6)}.0 MB"

    


          
