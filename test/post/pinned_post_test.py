from test.test_constants import *
from src.api.posts import Post,Media
import re
def test_postcreate_pinned():
    username="test"
    model_id=TEST_ID
    try:
        Post(PINNED_POSTS_EXAMPLE,model_id,username)
    except Exception as E:
        raise Exception(f"Exception: {E}\nPost Creation Failed")


def test_media_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(len(t.allmedia))==len(PINNED_POSTS_EXAMPLE["media"])

def test_post_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.post)==t._post


def test_modelid_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.model_id)==model_id


def test_username_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.username)==username

def test_archived_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.archived)==False

def test_text_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.text)==PINNED_POSTS_EXAMPLE.get("text")

def test_title_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.title)==PINNED_POSTS_EXAMPLE.get("title")

def test_ogresponse_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.ogresponsetype)==PINNED_POSTS_EXAMPLE.get("responseType")

def test_id_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.id)==PINNED_POSTS_EXAMPLE.get("id")

def test_date_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.date)==PINNED_POSTS_EXAMPLE.get("createdAt") or PINNED_POSTS_EXAMPLE.get("postedAt")


def test_value_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.value)=="free"

def test_price_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.price)==0


def test_paid_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.paid)==True


def test_fromuser_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.fromuser)==model_id

def test_preview_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    assert(t.preview)==PINNED_POSTS_EXAMPLE["preview"] 

def test_mediacanview_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    for ele in t.media:
        assert(ele.canview)==True


def test_mediaclass_pinned():
    username="test"
    model_id=TEST_ID
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    for ele in t.media:
        assert(isinstance(ele,Media))==True
 
 #Media Test
def test_mediaclass_pinned():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    try:
        media=Media(t.media[index],index,t)
    except:
        raise Exception()
    

def test_mediatype_pinned():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    mediaDict=PINNED_POSTS_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(mediaDict["type"])=="photo"
    assert(media.mediatype)=="images"


def test_mediaurl_pinned():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    mediaDict=PINNED_POSTS_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(re.search("http",media.url))!=None

def test_mediapost_pinned():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    mediaDict=PINNED_POSTS_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.post)==t

def test_media_id_pinned():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    mediaDict=PINNED_POSTS_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.id)==mediaDict["id"]

def test_medialen_pinned():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    mediaDict=PINNED_POSTS_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(len(media.post.allmedia))==len(PINNED_POSTS_EXAMPLE["media"])

def test_mediacount_pinned():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    mediaDict=PINNED_POSTS_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.count)==index+1

def test_mediapreview_pinned():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    mediaDict=PINNED_POSTS_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(PINNED_POSTS_EXAMPLE["preview"])==[]
    assert(media.preview)==0

def test_medialinked_pinned():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    mediaDict=PINNED_POSTS_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.linked)==None   

def test_mediamedia_pinned():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(PINNED_POSTS_EXAMPLE,model_id,username)
    mediaDict=PINNED_POSTS_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.media)==mediaDict