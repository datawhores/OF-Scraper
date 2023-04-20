import src.utils.download as download
import src.utils.paths as paths
from unittest.mock import patch,MagicMock
import platform
import pathlib
import src.utils.config as config
import os
from test_constants import *
from src.utils.download import createfilename


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
        "main_profile": "main_profile",
        "save_location": "/root/Data/ofscraper",
        "file_size_limit": "",
        "dir_format": "{model_username}/{responsetype}/{mediatype}/",
        "file_format": "{filename}.{ext}",
        "textlength": 0,
        "date": "MM-DD-YYYY",
        "metadata": METADATA_DC,
        "filter": "Images,Audios,Videos"
    }

   mocker.patch('src.utils.paths.config', new=migrationConfig)
   assert(str(paths.databasePathHelper("1111","test")))=="/root/test/metadata/user_data.db"    
   
