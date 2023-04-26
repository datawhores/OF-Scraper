from test.test_constants import *
from src.api.posts import Post,Media
import re
def test_postcreate_stories():
    username="test"
    model_id=TEST_ID
    try:
        Post(STORIES_EXAMPLE,model_id,username,"stories")
    except Exception as E:
        raise Exception(f"Exception: {E}\nPost Creation Failed")


def test_media_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(len(t.allmedia))==len(STORIES_EXAMPLE["media"])

def test_post_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.post)==t._post


def test_modelid_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.model_id)==model_id


def test_username_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.username)==username

def test_archived_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.archived)==False

def test_text_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.text)==(STORIES_EXAMPLE.get("text") or "")

def test_title_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.title)==STORIES_EXAMPLE.get("title")

def test_ogresponse_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.ogresponsetype)=="stories"

def test_id_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.id)==STORIES_EXAMPLE.get("id")

def test_date_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.date)==STORIES_EXAMPLE.get("createdAt") or STORIES_EXAMPLE.get("postedAt")


def test_value_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.value)=="free"

def test_price_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.price)==0


def test_paid_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.paid)==True


def test_fromuser_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.fromuser)==model_id

def test_preview_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.preview)==STORIES_EXAMPLE.get("preview")

def test_mediacanview_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    for ele in t.media:
        assert(ele.canview)==True


def test_mediaclass_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    for ele in t.media:
        assert(isinstance(ele,Media))==True
 
 #Media Test
def test_mediaclass_stories():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    try:
        media=Media(t.media[index],index,t)
    except:
        raise Exception()
    

def test_mediatype_stories():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    mediaDict=STORIES_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(mediaDict["type"])=="photo"
    assert(media.mediatype)=="images"


def test_mediaurl_stories():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    mediaDict=STORIES_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(re.search("http",media.url))!=None

def test_mediapost_stories():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    mediaDict=STORIES_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.post)==t

def test_media_id_stories():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    mediaDict=STORIES_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.id)==mediaDict["id"]

def test_medialen_stories():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    mediaDict=STORIES_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(len(media.post.allmedia))==len(STORIES_EXAMPLE["media"])


def test_mediacount_stories():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    mediaDict=STORIES_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.count)==index+1

def test_mediapreview_stories():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    mediaDict=STORIES_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(STORIES_EXAMPLE.get("preview"))==None
    assert(media.preview)==0

def test_medialinked_stories():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    mediaDict=STORIES_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.linked)==None   

def test_mediamedia_stories():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    mediaDict=STORIES_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.media)==mediaDict