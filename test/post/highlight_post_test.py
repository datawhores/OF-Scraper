from test.test_constants import *
from src.api.posts import Post,Media
import re
def test_postcreate_highlights():
    username="test"
    model_id=TEST_ID
    try:
        Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    except Exception as E:
        raise Exception(f"Exception: {E}\nPost Creation Failed")


def test_media_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(len(t.allmedia))==1

def test_post_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.post)==t._post


def test_modelid_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.model_id)==model_id


def test_username_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.username)==username

def test_archived_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.archived)==False

def test_text_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.text)==(HIGHLIGHT_EXAMPLE.get("text") or "")

def test_title_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.title)==HIGHLIGHT_EXAMPLE.get("title")

def test_ogresponse_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.ogresponsetype)=="highlights"

def test_id_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.id)==HIGHLIGHT_EXAMPLE.get("id")

def test_date_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.date)==HIGHLIGHT_EXAMPLE.get("createdAt") or HIGHLIGHT_EXAMPLE.get("postedAt")


def test_value_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.value)=="free"

def test_price_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.price)==0


def test_paid_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.paid)==True


def test_fromuser_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.fromuser)==model_id

def test_preview_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    assert(t.preview)==HIGHLIGHT_EXAMPLE.get("preview")

def test_mediacanview_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    for ele in t.media:
        assert(ele.canview)==True


def test_mediaclass_highlights():
    username="test"
    model_id=TEST_ID
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    for ele in t.media:
        assert(isinstance(ele,Media))==True
 
 #Media Test
def test_mediaclass_highlights():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    try:
        media=Media(t.media[index],index,t)
    except:
        raise Exception()
    

def test_mediatype_highlights():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    mediaDict={"url":HIGHLIGHT_EXAMPLE["cover"],"type":"photo"}
    media=Media(mediaDict,index,t)
    assert(mediaDict["type"])=="photo"
    assert(media.mediatype)=="images"


def test_mediaurl_highlights():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    mediaDict={"url":HIGHLIGHT_EXAMPLE["cover"]}
    media=Media(mediaDict,index,t)
    assert(re.search("http",media.url))!=None

def test_mediapost_highlights():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    mediaDict={"url":HIGHLIGHT_EXAMPLE["cover"]}
    media=Media(mediaDict,index,t)
    assert(media.post)==t

def test_media_id_highlights():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    mediaDict={"url":HIGHLIGHT_EXAMPLE["cover"]}
    media=Media(mediaDict,index,t)
    assert(media.id)==mediaDict.get("id")

def test_medialen_highlights():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    mediaDict={"url":HIGHLIGHT_EXAMPLE["cover"]}
    media=Media(mediaDict,index,t)
    assert(len(media.post.allmedia))==1


def test_mediacount_highlights():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    mediaDict={"url":HIGHLIGHT_EXAMPLE["cover"]}
    media=Media(mediaDict,index,t)
    assert(media.count)==index+1

def test_mediapreview_highlights():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    mediaDict={"url":HIGHLIGHT_EXAMPLE["cover"]}
    media=Media(mediaDict,index,t)
    assert(HIGHLIGHT_EXAMPLE.get("preview"))==None
    assert(media.preview)==0

def test_medialinked_highlights():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    mediaDict={"url":HIGHLIGHT_EXAMPLE["cover"]}
    media=Media(mediaDict,index,t)
    assert(media.linked)==None   

def test_mediamedia_highlights():
    username="test"
    model_id=TEST_ID
    index=0
    t=Post(HIGHLIGHT_EXAMPLE,model_id,username,"highlights")
    mediaDict={"url":HIGHLIGHT_EXAMPLE["cover"]}
    media=Media(mediaDict,index,t)
    assert(media.media)==mediaDict