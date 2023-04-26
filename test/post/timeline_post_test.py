from test.test_constants import *
from src.api.posts import Post,Media
import re
def test_postcreate_timeline():
    username="test"
    model_id=TEST_ID
    try:
        Post(TIMELINE_EXAMPLE,model_id,username)
    except Exception as E:
        raise Exception(f"Exception: {E}\nPost Creation Failed")


def test_media_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(len(t.allmedia))==len(TIMELINE_EXAMPLE["media"])

def test_post_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.post)==t._post


def test_modelid_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.model_id)==model_id


def test_username_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.username)==username

def test_archived_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.archived)==False

def test_text_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.text)==TIMELINE_EXAMPLE.get("text")

def test_title_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.title)==TIMELINE_EXAMPLE.get("title")

def test_ogresponse_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.ogresponsetype)==TIMELINE_EXAMPLE.get("responseType")

def test_id_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.id)==TIMELINE_EXAMPLE.get("id")

def test_date_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.date)==TIMELINE_EXAMPLE.get("createdAt") or TIMELINE_EXAMPLE.get("postedAt")


def test_value_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.value)=="free"

def test_price_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.price)==0


def test_paid_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.paid)==True


def test_fromuser_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.fromuser)==model_id

def test_preview_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    assert(t.preview)==TIMELINE_EXAMPLE["preview"] 

def test_mediacanview_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    for ele in t.media:
        assert(ele.canview)==True


def test_mediaclass_timeline():
    username="test"
    model_id=TEST_ID
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    for ele in t.media:
        assert(isinstance(ele,Media))==True
 
 #Media Test
def test_mediaclass_timeline():
    username="test"
    model_id=TEST_ID
    index=1
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    try:
        media=Media(t.media[index],index,t)
    except:
        raise Exception()
    

def test_mediatype_timeline():
    username="test"
    model_id=TEST_ID
    index=1
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    mediaDict=TIMELINE_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(mediaDict["type"])=="photo"
    assert(media.mediatype)=="images"


def test_mediaurl_timeline():
    username="test"
    model_id=TEST_ID
    index=1
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    mediaDict=TIMELINE_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(re.search("http",media.url))!=None

def test_mediapost_timeline():
    username="test"
    model_id=TEST_ID
    index=1
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    mediaDict=TIMELINE_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.post)==t

def test_media_id_timeline():
    username="test"
    model_id=TEST_ID
    index=1
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    mediaDict=TIMELINE_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.id)==mediaDict["id"]

def test_medialen_timeline():
    username="test"
    model_id=TEST_ID
    index=1
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    mediaDict=TIMELINE_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(len(media.post.allmedia))==len(TIMELINE_EXAMPLE["media"])


def test_mediacount_timeline():
    username="test"
    model_id=TEST_ID
    index=1
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    mediaDict=TIMELINE_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.count)==index+1

def test_mediapreview_timeline():
    username="test"
    model_id=TEST_ID
    index=1
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    mediaDict=TIMELINE_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(TIMELINE_EXAMPLE["preview"])==[]
    assert(media.preview)==0

def test_medialinked_timeline():
    username="test"
    model_id=TEST_ID
    index=1
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    mediaDict=TIMELINE_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.linked)==None   

def test_mediamedia_timeline():
    username="test"
    model_id=TEST_ID
    index=1
    t=Post(TIMELINE_EXAMPLE,model_id,username)
    mediaDict=TIMELINE_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.media)==mediaDict