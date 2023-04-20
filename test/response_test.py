from test_constants import *
from src.utils.download import createfilename,geturlfilename
from src.api.timeline import parse_posts
def test_default_timelinefilename_expection(mocker):
    posts=parse_posts([TIMELINE_EXAMPLE])
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
    mocker.patch("src.utils.download.read_config",return_value=migrationConfig)
    try:
        createfilename(posts[0],"test","1111","mkv")
    except Exception as exc:
        assert False, f"{exc}"


def test_default_timelinefilename_value(mocker):
    posts=parse_posts([TIMELINE_EXAMPLE])
    ele=posts[0]
   
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
    mocker.patch("src.utils.download.read_config",return_value=migrationConfig)
    assert(createfilename(ele,"test","1111","mkv"))==f"{geturlfilename(ele['url'])}.mkv"


      
       