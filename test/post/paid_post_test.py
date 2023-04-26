from test.test_constants import *
from src.api.posts import Post,Media
import re
def test_postcreate_paid():
    username="test"
    model_id=TEST_ID
    try:
        Post(PAID_EXAMPLE,model_id,username)
    except Exception as E:
        raise Exception(f"Exception: {E}\nPost Creation Failed")


def test_media_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(len(t.allmedia))==len(PAID_EXAMPLE["media"])

def test_post_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.post)==t._post


def test_modelid_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.model_id)==model_id


def test_username_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.username)==username

def test_archived_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.archived)==False

def test_text_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.text)==PAID_EXAMPLE.get("text")

def test_title_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.title)==PAID_EXAMPLE.get("title")

def test_ogresponse_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.ogresponsetype)==PAID_EXAMPLE.get("responseType")

def test_id_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.id)==PAID_EXAMPLE.get("id")

def test_date_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.date)==PAID_EXAMPLE.get("createdAt") or PAID_EXAMPLE.get("postedAt")


def test_value_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.value)=="paid"

def test_price_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.price)==PAID_EXAMPLE["price"]


def test_paid_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.paid)==True


def test_fromuser_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.fromuser)==model_id

def test_preview_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    assert(t.preview)==PAID_EXAMPLE.get("preview")

def test_mediacanview_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    for ele in t.media:
        assert(ele.canview)==True


def test_mediaclass_paid():
    username="test"
    model_id=TEST_ID
    t=Post(PAID_EXAMPLE,model_id,username)
    for ele in t.media:
        assert(isinstance(ele,Media))==True
 
 #Media Test
def test_mediaclass_paid():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PAID_EXAMPLE,model_id,username)
    try:
        media=Media(t.media[index],index,t)
    except:
        raise Exception()
    

def test_mediatype_paid():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PAID_EXAMPLE,model_id,username)
    mediaDict=PAID_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(mediaDict["type"])=="video"
    assert(media.mediatype)=="videos"


def test_mediaurl_paid():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PAID_EXAMPLE,model_id,username)
    mediaDict=PAID_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(re.search("http",media.url))!=None

def test_mediapost_paid():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PAID_EXAMPLE,model_id,username)
    mediaDict=PAID_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.post)==t

def test_media_id_paid():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PAID_EXAMPLE,model_id,username)
    mediaDict=PAID_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.id)==mediaDict["id"]

def test_medialen_paid():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PAID_EXAMPLE,model_id,username)
    mediaDict=PAID_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(len(media.post.allmedia))==len(PAID_EXAMPLE["media"])


def test_mediacount_paid():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PAID_EXAMPLE,model_id,username)
    mediaDict=PAID_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.count)==index+1

def test_mediapreview_paid():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PAID_EXAMPLE,model_id,username)
    mediaDict=PAID_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(PAID_EXAMPLE.get("preview"))==None
    assert(media.preview)==0
def test_medialinked_paid():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PAID_EXAMPLE,model_id,username)
    mediaDict=PAID_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.linked)==None   

def test_mediamedia_paid():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PAID_EXAMPLE,model_id,username)
    mediaDict=PAID_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.media)==mediaDict