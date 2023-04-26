from test.test_constants import *
from src.api.posts import Post,Media
import re
def test_postcreate_archived():
    username="test"
    model_id=TEST_ID
    try:
        Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    except Exception as E:
        raise Exception(f"Exception: {E}\nPost Creation Failed")


def test_media_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(len(t.allmedia))==len(ARCHIVED_POST_EXAMPLE["media"])

def test_post_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.post)==t._post


def test_modelid_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.model_id)==model_id


def test_username_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.username)==username

def test_archived_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.archived)==True

def test_text_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.text)==ARCHIVED_POST_EXAMPLE.get("text")

def test_title_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.title)==ARCHIVED_POST_EXAMPLE.get("title")

def test_ogresponse_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.ogresponsetype)==ARCHIVED_POST_EXAMPLE.get("responseType")

def test_id_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.id)==ARCHIVED_POST_EXAMPLE.get("id")

def test_date_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.date)==ARCHIVED_POST_EXAMPLE.get("createdAt") or ARCHIVED_POST_EXAMPLE.get("postedAt")


def test_value_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.value)=="free"

def test_price_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.price)==0


def test_paid_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.paid)==True


def test_fromuser_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.fromuser)==model_id

def test_preview_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    assert(t.preview)==ARCHIVED_POST_EXAMPLE["preview"] 

def test_mediacanview_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    for ele in t.media:
        assert(ele.canview)==True


def test_mediaclass_archived():
    username="test"
    model_id=TEST_ID
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    for ele in t.media:
        assert(isinstance(ele,Media))==True
 
 #Media Test
def test_mediaclass_archived():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    try:
        media=Media(t.media[index],index,t)
    except:
        raise Exception()
    

def test_mediatype_archived():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    mediaDict=ARCHIVED_POST_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(mediaDict["type"])=="video"
    assert(media.mediatype)=="videos"


def test_mediaurl_archived():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    mediaDict=ARCHIVED_POST_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(re.search("http",media.url))!=None

def test_mediapost_archived():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    mediaDict=ARCHIVED_POST_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.post)==t

def test_media_id_archived():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    mediaDict=ARCHIVED_POST_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.id)==mediaDict["id"]

def test_medialen_archived():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    mediaDict=ARCHIVED_POST_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(len(media.post.allmedia))==len(ARCHIVED_POST_EXAMPLE["media"])

def test_mediacount_archived():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    mediaDict=ARCHIVED_POST_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.count)==index+1

def test_mediapreview_archived():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    mediaDict=ARCHIVED_POST_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(ARCHIVED_POST_EXAMPLE["preview"])==[]
    assert(media.preview)==0

def test_medialinked_archived():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    mediaDict=ARCHIVED_POST_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.linked)==None   

def test_mediamedia_archived():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(ARCHIVED_POST_EXAMPLE,model_id,username)
    mediaDict=ARCHIVED_POST_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.media)==mediaDict