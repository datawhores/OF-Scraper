from test.test_constants import *
from ofscraper.utils.profiles import *
import pathlib
def test_profile_count(mocker):
    assert(len(get_profiles()))==3