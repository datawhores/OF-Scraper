
from test.test_constants import *
import ofscraper.api.me as me
import ofscraper.api.profile as profile
from xxhash import xxh32
import tempfile

def test_me():
     assert(me.parse_user(OWNPROFILE_DICT_EXAMPLE))==('simpsimp',"u300")


def test_parse_profile():
    profile_=USERPROFILE_EXAMPLE_DICT
  
  
    assert(profile.parse_profile(profile_))[0][0]["url"]==USERPROFILE_EXAMPLE_DICT["avatar"]

def test_parse_profile2():
    profile_=USERPROFILE_EXAMPLE_DICT
    assert(profile.parse_profile(profile_))[0][0]["responsetype"]=="profile"

def test_parse_profile3():
    profile_=USERPROFILE_EXAMPLE_DICT
    assert(set(profile.parse_profile
    (profile_)[0][0].keys()))==set(["url","responsetype","mediatype","value","createdAt","text","id"])

def test_parse_profile4():
    profile_=USERPROFILE_EXAMPLE_DICT
    assert(profile.parse_profile
    (profile_)[0][0]["id"])==xxh32(USERPROFILE_EXAMPLE_DICT["avatar"]).hexdigest()
def test_parse_profile5():
    profile_=USERPROFILE_EXAMPLE_DICT
    if USERPROFILE_EXAMPLE_DICT.get("profile"):
        assert(set(profile.parse_profile
        (profile_)[0][1].keys()))==set(["url","responsetype","mediatype","value","createdAt","text","id"])    
def test_parse_profile6():
    profile_=USERPROFILE_EXAMPLE_DICT
    assert(profile.parse_profile
    (profile_)[1][1])==USERPROFILE_EXAMPLE_DICT["username"]

def test_parse_profile7():
    profile_=USERPROFILE_EXAMPLE_DICT
    assert(profile.parse_profile
    (profile_)[1][2])==USERPROFILE_EXAMPLE_DICT["id"]