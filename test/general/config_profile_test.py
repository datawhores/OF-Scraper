from test.test_constants import *
from src.utils.profiles import *
import pathlib
def test_profile_count(mocker):
    mocker.patch("src.utils.profiles.pathlib.Path.glob",return_value=[pathlib.Path("1"),pathlib.Path("1"),pathlib.Path("1")])
    mocker.patch("src.utils.profiles.pathlib.Path.is_dir",return_value=True)
    assert(len(get_profiles()))==3