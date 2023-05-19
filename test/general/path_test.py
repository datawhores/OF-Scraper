
from unittest.mock import patch,MagicMock
from unittest import mock
import platform
import pathlib
import os
import tempfile
from pytest_check import check
import pytest
import arrow
import logging
import ofscraper.utils.download as download
import ofscraper.utils.paths as paths

from test.test_constants import *
from ofscraper.api.posts import Post,Media
from ofscraper.utils.dates import convert_local_time




#Word split



def test_windows_trunicate(mocker):
    with patch('platform.system', MagicMock(return_value="Windows")):
        long_path=pathlib.Path(f"{WINDOWS_LONGPATH}.mkv")
        trunicated=paths.trunicate(long_path)
        with check:
            assert(len(str(trunicated)))<=256
        with check:
            assert(long_path.parent)==trunicated.parent
        with check:
            assert(long_path.suffix)==trunicated.suffix


def test_windows_trunicate_256(mocker):
    with patch('platform.system', MagicMock(return_value="Windows")):
        pathbase=WINDOWS_LONGPATH[:252]
        long_path=pathlib.Path(f"{pathbase}.mkv")
        trunicated=paths.trunicate(long_path)
        with check:
            assert(len(str(long_path)))==256
        with check:
            assert(len(str(trunicated)))==256
        with check: 
            assert(long_path.parent)==trunicated.parent
        with check:
            assert(long_path.suffix)==trunicated.suffix


def test_windows_trunicate_small(mocker):
    with patch('platform.system', MagicMock(return_value="Windows")):
        pathbase=WINDOWS_LONGPATH[:200]
        long_path=pathlib.Path(f"{pathbase}.mkv")
        trunicated=paths.trunicate(long_path)
        with check:
            assert(len(str(long_path)))==204        
        with check:
            assert(len(str(trunicated)))==204
        with check: 
            assert(long_path.parent)==trunicated.parent
        with check:
            assert(long_path.suffix)==trunicated.suffix


def test_linux_trunicate(mocker):
    with patch('platform.system', MagicMock(return_value="Linux")):
        long_path=pathlib.Path(f"{LINUX_LONGPATH}.mkv")
        trunicated=paths.trunicate(long_path)
        with check:
            assert(len(str(trunicated.name).encode("utf8")))<=255
        with check:
            assert(long_path.parent)==trunicated.parent
        with check:
            assert(long_path.suffix)==trunicated.suffix


def test_linux_trunicate_255(mocker):
    with patch('platform.system', MagicMock(return_value="Linux")):
        dirLength=len(str(pathlib.Path(LINUX_LONGPATH).parent).encode("utf8"))
        extLength=len(".mkv".encode("utf8"))
        maxlenth=255
        pathbase=(LINUX_LONGPATH.encode("utf8")[:dirLength+1+maxlenth
        -extLength]).decode()
        long_path=pathlib.Path(f"{pathbase}.mkv")
        trunicated=paths.trunicate(long_path)
        with check:
            assert(len(str(long_path.name).encode("utf8")))==maxlenth
        with check:
            assert(len(str(trunicated.name).encode("utf8")))==maxlenth
        with check: 
            assert(long_path.parent)==trunicated.parent
        with check:
            assert(long_path.suffix)==trunicated.suffix

def test_linux_trunicate_small(mocker):
    with patch('platform.system', MagicMock(return_value="Linux")):
        dirLength=len(str(pathlib.Path(LINUX_LONGPATH).parent).encode("utf8"))
        extLength=len(".mkv".encode("utf8"))
        maxlenth=200
        pathbase=(LINUX_LONGPATH.encode("utf8")[:dirLength+1+maxlenth
        -extLength]).decode()
        long_path=pathlib.Path(f"{pathbase}.mkv")
        trunicated=paths.trunicate(long_path)
        with check:
            assert(len(str(long_path.name).encode("utf8")))==maxlenth
        with check:
            assert(len(str(trunicated.name).encode("utf8")))==maxlenth
        with check: 
            assert(long_path.parent)==trunicated.parent
        with check:
            assert(long_path.suffix)==trunicated.suffix

def test_user_data_dc_db_str(mocker):
   migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILE_FORMAT_DEFAULT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DC,
        "filter": FILTER_DEFAULT
    }

   mocker.patch('ofscraper.utils.paths.config_.read_config', return_value=migrationConfig)
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
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILE_FORMAT_DEFAULT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    mocker.patch('ofscraper.utils.download.config_.read_config', return_value=migrationConfig)
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    print(t.media[0].filename)
    assert(download.createfilename(t.media[0],username,model_id,"mkv"))==f"{t.media[0].filename}.mkv"

def test_createfilename_allkeys(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_VALID_ALL,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }

    mocker.patch('ofscraper.utils.download.config_.read_config', return_value=migrationConfig)
    username="test"
    model_id=TEST_ID
    try:
        t=Post(TIMELINE_EXAMPLE,model_id,username)
        assert(download.createfilename(t.media[0],username,model_id,"mkv"))
    except:
        raise Exception

def test_createfilename_invalid(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_ALLVALIDWTHINVALID,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }

    mocker.patch('ofscraper.utils.download.config_.read_config', return_value=migrationConfig)
    username="test"
    model_id=TEST_ID
    with pytest.raises(Exception):
        t=Post(TIMELINE_EXAMPLE,model_id,username)
        assert(download.createfilename(t.media[0],username,model_id,"mkv"))

def test_create_txt(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    mocker.patch('ofscraper.utils.download.config_.read_config', return_value=migrationConfig)
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    print(t.media[0].filename)
    assert(download.createfilename(t.media[0],username,model_id,"mkv"))==f"{t.media[0].text}_1.mkv"
#Test postid counter
def test_create_postid_counter(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_POSTID,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    mocker.patch('ofscraper.utils.download.config_.read_config', return_value=migrationConfig)
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(len(t.media))>1


def test_create_postid_name(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_POSTID,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    mocker.patch('ofscraper.utils.download.config_.read_config', return_value=migrationConfig)
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)

    assert(download.createfilename(t.media[0],username,model_id,"mkv"))==f"{t.media[0].id}_1.mkv"


def test_create_postid_name2(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_POSTID,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    mocker.patch('ofscraper.utils.download.config_.read_config', return_value=migrationConfig)
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    mocker.patch('ofscraper.api.posts.Post.allmedia', new=[t.allmedia[0]])
    assert(download.createfilename(t.media[0],username,model_id,"mkv"))==f"{t.media[0].id}.mkv"







#Test text counter
def test_create_text_counter(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    mocker.patch('ofscraper.utils.download.config_.read_config', return_value=migrationConfig)
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(len(t.media))>1






def test_create_text_name(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    mocker.patch('ofscraper.utils.download.config_.read_config', return_value=migrationConfig)
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)

    assert(download.createfilename(t.media[0],username,model_id,"mkv"))==f"{t.media[0].text}_1.mkv"


def test_create_text_name2(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    mocker.patch('ofscraper.utils.download.config_.read_config', return_value=migrationConfig)
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    mocker.patch('ofscraper.api.posts.Post.allmedia', new=[t.allmedia[0]])
    assert(download.createfilename(t.media[0],username,model_id,"mkv"))==f"{t.media[0].text}.mkv"



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

    


          
