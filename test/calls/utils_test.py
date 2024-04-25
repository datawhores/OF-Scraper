# import re
# import pathlib
# import os
# import tempfile
# from pytest_check import check
# import pytest
# import arrow
# import logging
# import random
# import string
#  import ofscraper.download.download as download
# import ofscraper.utils.paths as paths
# from random_unicode_emoji import random_emoji

# from  test_.test_constants import *
# from ofscraper.classes.posts import Post
# from ofscraper.classes.media import Media
# from ofscraper.utils.dates import convert_local_time
# # import ofscraper.utils.logger as logger
#  import ofscraper.download.download as download

# def test_user_data_dc_db_str(mocker):
#     migrationConfig={
#         "main_profile": PROFILE_DEFAULT,
#         "save_location": SAVE_PATH_DEFAULT,
#         "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
#         "dir_format": DIR_FORMAT_DEFAULT,
#         "file_format": FILE_FORMAT_DEFAULT,
#         "textlength": TEXTLENGTH_DEFAULT,
#         "date": DATE_DEFAULT,
#         "metadata": METADATA_DC,
#         "filter": FILTER_DEFAULT,
#         "key-mode-default": "manual"
#     }
#     logger.init_logger(logging.getLogger(__package__))
#     MagicMock()
#     # mocker.patch('ofscraper.utils.paths.config_.read_config', return_value=migrationConfig)
#     # mocker.patch('ofscraper.utils.paths.profiles.get_my_info', return_value=ME)
#     # media=Post( TIMELINE_EXAMPLE,"dd","dd").media[0]

#     # try:
#     #     assert(download.main_download_downloader("s",media,"t",0,"dd","ddd","dd"))
#     # except:
#     #     None

# from example import *

# def test_func1__should_call_func2(mocker):
#     mock_func2=MagicMock("example.func2")
#     func1()
#     mock_func2.assert_called_once()

# def test_func1__should_not_call_func2(mocker):
#     func1(False)
#     mock_func2=MagicMock("example.func2")
#     mock_func2.assert_not_called()
