import json
import tempfile

from pytest_check import check

import ofscraper.config.config as config_
import ofscraper.utils.paths.paths as paths_
from ofscraper.config.config import *
from ofscraper.config.data import *
from ofscraper.const.test_constants import *
from ofscraper.utils.profiles2.profiles import *

# def test_current_schema(mocker):
#     migrationConfig={"config":{
#         "main_profile": PROFILE_DEFAULT,
#         "save_location": SAVE_PATH_DEFAULT,
#         "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
#         "dir_format": DIR_FORMAT_DEFAULT,
#         "file_format": FILEFORMAT_POSTID,
#         "textlength": TEXTLENGTH_DEFAULT,
#         "date": DATE_DEFAULT,
#         "metadata": METADATA_DEFAULT,
#         "filter": FILTER_DEFAULT,
#         "mp4decrypt":MP4DECRYPT_DEFAULT
#     }}

#     currentConfig=get_current_data.schema(migrationConfig)

#     assert(sorted(set(currentConfig["config"].keys())))==sorted(set(data.KEYS))


def test_new_config_location(mocker):
    migrationConfig = {
        "config": {
            "main_profile": PROFILE_DEFAULT,
            "save_location": SAVE_PATH_DEFAULT,
            "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        }
    }
    currentConfig = get_current_config_schema(migrationConfig)
    with tempfile.TemporaryDirectory() as p:
        mocker.patch(
            "ofscraper.utils.args.getargs", return_value=args_.getargs(["--config", p])
        )
        configPath = paths_.get_config_path()
        configPath.parent.mkdir(parents=True, exist_ok=True)

        with open(configPath, "w") as w:
            w.write(json.dumps(currentConfig))

        new_config = config_.read_config()
        for key in new_config:
            with check:
                assert (new_config[key]) == currentConfig["config"][key]


# def test_current_schema2(mocker):
#     migrationConfig={"config":{
#         "main_profile": PROFILE_DEFAULT,
#         "save_location": SAVE_PATH_DEFAULT,
#         "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
#     }}
#     currentConfig=get_current_data.schema(migrationConfig)

#     assert(sorted(set(currentConfig["config"].keys())))==sorted(set(data.KEYS))


def test_savelocation(mocker):
    assert (get_save_location(None)) == SAVE_PATH_DEFAULT


def test_savelocation2(mocker):
    config = {"save_location": SAVE_LOCATION_ALT}
    assert (get_save_location(config)) == SAVE_LOCATION_ALT


def test_savelocation3(mocker):
    config = {}
    assert (get_save_location(config)) == SAVE_PATH_DEFAULT


def test_mainprofile(mocker):
    assert (get_main_profile(None)) == PROFILE_DEFAULT


def test_mainprofile2(mocker):
    config = {"main_profile": PROFILE_ALT}
    assert (get_main_profile(config)) == PROFILE_ALT


def test_mainprofile3(mocker):
    config = {}
    assert (get_main_profile(config)) == PROFILE_DEFAULT


def test_filesize(mocker):
    assert (get_filesize_limit(None)) == FILE_SIZE_LIMIT_DEFAULT


def test_filesize2(mocker):
    config = {"file_size_limit": FILE_SIZE_ALT}
    assert (get_filesize_limit(config)) == FILE_SIZE_ALT


def test_filesize3(mocker):
    config = {}
    assert (get_filesize_limit(config)) == FILE_SIZE_LIMIT_DEFAULT


def test_dirformat(mocker):
    assert (get_dirformat(None)) == DIR_FORMAT_DEFAULT


def test_dirformat2(mocker):
    config = {"dir_format": DIR_FORMAT_ALLVALID}
    assert (get_dirformat(config)) == DIR_FORMAT_ALLVALID


def test_dirformat3(mocker):
    config = {}
    assert (get_dirformat(config)) == DIR_FORMAT_DEFAULT


def test_fileformat(mocker):
    assert (get_fileformat(None)) == FILE_FORMAT_DEFAULT


def test_fileformat2(mocker):
    config = {"file_format": FILEFORMAT_VALID_ALL}
    assert (get_fileformat(config)) == FILEFORMAT_VALID_ALL


def test_fileformat3(mocker):
    config = {}
    assert (get_fileformat(config)) == FILE_FORMAT_DEFAULT


def test_textlength(mocker):
    assert (get_textlength(None)) == TEXTLENGTH_DEFAULT


def test_textlength2(mocker):
    config = {"textlength": TEXTLENGTH_ALT}
    assert (get_textlength(config)) == TEXTLENGTH_ALT


def test_textlength3(mocker):
    config = {}
    assert (get_textlength(config)) == TEXTLENGTH_DEFAULT


def test_date(mocker):
    assert (get_date(None)) == DATE_DEFAULT


def test_date2(mocker):
    config = {"date": DATE_ALT}
    assert (get_date(config)) == DATE_ALT


def test_date3(mocker):
    config = {}
    assert (get_date(config)) == DATE_DEFAULT


def test_metadata(mocker):
    assert (get_metadata(None)) == METADATA_DEFAULT


def test_metadata2(mocker):
    config = {"metadata": METADATA_ALLVALID}
    assert (get_metadata(config)) == METADATA_ALLVALID


def test_metadata3(mocker):
    config = {}
    assert (get_metadata(config)) == METADATA_DEFAULT


def test_mp4decrypt(mocker):
    assert (get_mp4decrypt(None)) == MP4DECRYPT_DEFAULT


def test_mp4decrypt2(mocker):
    config = {"mp4decrypt": ALT_MP4DECRYPT}
    assert (get_mp4decrypt(config)) == ALT_MP4DECRYPT


def test_mp4decrypt3(mocker):
    config = {}
    assert (get_mp4decrypt(config)) == MP4DECRYPT_DEFAULT


def test_ffmpeg(mocker):
    assert (get_ffmpeg(None)) == FFMPEG_DEFAULT


def test_ffmpeg2(mocker):
    config = {"ffmpeg": ALT_FFMPEG}
    assert (get_ffmpeg(config)) == ALT_FFMPEG


def test_ffmpeg3(mocker):
    config = {}
    assert (get_ffmpeg(config)) == FFMPEG_DEFAULT


def test_filter(mocker):
    assert (get_filter(None)) == FILTER_DEFAULT


def test_filter2(mocker):
    config = {"filter": []}
    assert (get_filter(config)) == []


def test_filter3(mocker):
    config = {}
    assert (get_filter(config)) == FILTER_DEFAULT


def test_timelineresponse(mocker):
    assert (get_timeline_responsetype(None)) == RESPONSE_TYPE_DEFAULT["timeline"]


def test_timelineresponse2(mocker):
    config = {"responsetype": {"timeline": RESPONSE_TYPE_DEFAULT["archived"]}}
    assert (get_timeline_responsetype(config)) == RESPONSE_TYPE_DEFAULT["archived"]


def test_timelineresponse3(mocker):
    config = {}
    assert (get_timeline_responsetype(config)) == RESPONSE_TYPE_DEFAULT["timeline"]


def test_archived_response(mocker):
    assert (get_archived_responsetype(None)) == RESPONSE_TYPE_DEFAULT["archived"]


def test_archived2(mocker):
    config = {"responsetype": {"archived": RESPONSE_TYPE_DEFAULT["timeline"]}}
    assert (get_archived_responsetype(config)) == RESPONSE_TYPE_DEFAULT["timeline"]


def test_archivedresponse3(mocker):
    config = {}
    assert (get_archived_responsetype(config)) == RESPONSE_TYPE_DEFAULT["archived"]


def test_stories_response(mocker):
    assert (get_stories_responsetype(None)) == RESPONSE_TYPE_DEFAULT["stories"]


def test_stories2(mocker):
    config = {"responsetype": {"stories": RESPONSE_TYPE_DEFAULT["timeline"]}}
    assert (get_stories_responsetype(config)) == RESPONSE_TYPE_DEFAULT["timeline"]


def test_storiesresponse3(mocker):
    config = {}
    assert (get_stories_responsetype(config)) == RESPONSE_TYPE_DEFAULT["stories"]


def test_highlights_response(mocker):
    assert (get_highlights_responsetype(None)) == RESPONSE_TYPE_DEFAULT["highlights"]


def test_highlights2(mocker):
    config = {"responsetype": {"highlights": RESPONSE_TYPE_DEFAULT["timeline"]}}
    assert (get_highlights_responsetype(config)) == RESPONSE_TYPE_DEFAULT["timeline"]


def test_highlightsresponse3(mocker):
    config = {}
    assert (get_highlights_responsetype(config)) == RESPONSE_TYPE_DEFAULT["highlights"]


def test_paid_response(mocker):
    assert (get_paid_responsetype(None)) == RESPONSE_TYPE_DEFAULT["paid"]


def test_paid2(mocker):
    config = {"responsetype": {"paid": RESPONSE_TYPE_DEFAULT["timeline"]}}
    assert (get_paid_responsetype(config)) == RESPONSE_TYPE_DEFAULT["timeline"]


def test_paidresponse3(mocker):
    config = {}
    assert (get_paid_responsetype(config)) == RESPONSE_TYPE_DEFAULT["paid"]


def test_messages_response(mocker):
    assert (get_messages_progress_responsetype(None)) == RESPONSE_TYPE_DEFAULT[
        "message"
    ]


def test_messages2(mocker):
    config = {"responsetype": {"message": RESPONSE_TYPE_DEFAULT["timeline"]}}
    assert (get_messages_progress_responsetype(config)) == RESPONSE_TYPE_DEFAULT[
        "timeline"
    ]


def test_messagesresponse3(mocker):
    config = {}
    assert (get_messages_progress_responsetype(config)) == RESPONSE_TYPE_DEFAULT[
        "message"
    ]


def test_profiles_response(mocker):
    assert (get_profile_responsetype(None)) == RESPONSE_TYPE_DEFAULT["profile"]


def test_profiles2(mocker):
    config = {"responsetype": {"profile": RESPONSE_TYPE_DEFAULT["timeline"]}}
    assert (get_profile_responsetype(config)) == RESPONSE_TYPE_DEFAULT["timeline"]


def test_profilesresponse3(mocker):
    config = {}
    assert (get_profile_responsetype(config)) == RESPONSE_TYPE_DEFAULT["profile"]


def test_pinned_response(mocker):
    assert (get_pinned_responsetype(None)) == RESPONSE_TYPE_DEFAULT["pinned"]


def test_pinned_response2(mocker):
    config = {"responsetype": {"profile": RESPONSE_TYPE_DEFAULT["timeline"]}}
    assert (get_pinned_responsetype(config)) == RESPONSE_TYPE_DEFAULT["timeline"]


def test_pinned_response3(mocker):
    config = {}
    assert (get_pinned_responsetype(config)) == RESPONSE_TYPE_DEFAULT["pinned"]
