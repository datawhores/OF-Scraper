from test.test_constants import *
from ofscraper.api.posts import Post,Media
import re
import ofscraper.utils.args as args_
from pytest_check import check
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
    assert(len(t.post_media))==len(STORIES_EXAMPLE["media"])

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
    assert(t.text)==None

def test_text_stories2():

    username="test"
    model_id=TEST_ID
    index=0

    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    mediaDict=STORIES_EXAMPLE["media"][index]
    media=Media(mediaDict,index,t)
    assert(media.text_.find(media.filename))==0
def test_title_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.title)==STORIES_EXAMPLE.get("title")

def test_ogresponse_stories():
    username="test"
    model_id=TEST_ID
    t=Post(STORIES_EXAMPLE,model_id,username,"stories")
    assert(t.responsetype_)=="stories"

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
    assert(len(media.post.post_media))==len(STORIES_EXAMPLE["media"])


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

def test_stories_text_wordtrunicate(mocker):
    length=TEXTLENGTH_ALT2
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_ALT2,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    args_.getargs([])
    mocker.patch('ofscraper.api.posts.config.read_config', return_value=migrationConfig)
    post=mocker.PropertyMock()
    post.post_media=["",""]
    mocker.patch.object(Media,"text",new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
    t=Media(None,2,post)
    wordarray=list(filter(lambda x:len(x)!=0,re.split("( )", t.text_)))
    with check:
        assert(len(wordarray))>= length-1
  
    with check:
        assert(len(wordarray))< length+1

def test_stories_text_wordtrunicate2(mocker):
    length=int(TEXTLENGTH_ALT2/2)
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    args_.getargs([])
    mocker.patch('ofscraper.api.posts.config.read_config', return_value=migrationConfig)
    post=mocker.PropertyMock()
    post.post_media=["",""]
    mocker.patch.object(Media,"text",new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
    t=Media(None,2,post)
    wordarray=list(filter(lambda x:len(x)!=0,re.split("( )", t.text_)))
    with check:
        assert(len(wordarray))>=length-1
  
    with check:
        assert(len(wordarray))<length+1

def test_stories_text_wordtrunicate3(mocker):
    length=TEXTLENGTH_DEFAULT
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    args_.getargs([])
    mocker.patch('ofscraper.api.posts.config.read_config', return_value=migrationConfig)
    post=mocker.PropertyMock()
    post.post_media=["",""]
    mocker.patch.object(Media,"text",new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
    t=Media(None,2,post)
    wordarray=list(filter(lambda x:len(x)!=0,re.split("( )", t.text_)))
    textarray=list(filter(lambda x:len(x)!=0,re.split("( )", f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")))
    with check:
        assert(len(wordarray))>=len(textarray)-1
    with check:
        assert(len(wordarray))<=len(textarray)+2

def test_stories_text_wordtrunicate4(mocker):
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_ALT2,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    args_.getargs([])
    mocker.patch('ofscraper.api.posts.config.read_config', return_value=migrationConfig)
    post=mocker.PropertyMock()
    post.post_media=[]
    mocker.patch.object(Media,"text",new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
    t=Media(None,0,post)
    wordarray=list(filter(lambda x:len(x)!=0,re.split("( )", t.text_)))
    with check:
        assert(len(wordarray))>=TEXTLENGTH_ALT2-1
  
    with check:
        assert(len(wordarray))<TEXTLENGTH_ALT2+1

def test_stories_text_wordtrunicate5(mocker):
    length=int(TEXTLENGTH_ALT2/2)
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    args_.getargs([])
    mocker.patch('ofscraper.api.posts.config.read_config', return_value=migrationConfig)
    post=mocker.PropertyMock()
    post.post_media=[]
    mocker.patch.object(Media,"text",new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
    t=Media(None,0,post)
    wordarray=list(filter(lambda x:len(x)!=0,re.split("( )", t.text_)))
    with check:
        assert(len(wordarray))>=length-1
  
    with check:
        assert(len(wordarray))<length+1

def test_stories_text_wordtrunicate6(mocker):
    length=TEXTLENGTH_DEFAULT
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    args_.getargs([])
    mocker.patch('ofscraper.api.posts.config.read_config', return_value=migrationConfig)
    post=mocker.PropertyMock()
    post.post_media=[]
    mocker.patch.object(Media,"text",new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
    t=Media(None,0,post)
    wordarray=list(filter(lambda x:len(x)!=0,re.split("( )", t.text_)))
    assert(len(wordarray))>=len("{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")


def test_stories_text_lettertrunicate(mocker):
    length=TEXTLENGTH_ALT
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_ALT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    args_.getargs(["--letter-count"])
    mocker.patch('ofscraper.api.posts.config.read_config', return_value=migrationConfig)
    post=mocker.PropertyMock()
    post.post_media=["",""]
    mocker.patch.object(Media,"text",new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
    t=Media(None,2,post)
    wordarray=t.text_
    assert(len(wordarray))==length
  
        

def test_stories_text_lettertrunicate2(mocker):
    length=int(TEXTLENGTH_ALT2/2)
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    args_.getargs(["--letter-count"])
    mocker.patch('ofscraper.api.posts.config.read_config', return_value=migrationConfig)
    post=mocker.PropertyMock()
    post.post_media=["",""]
    mocker.patch.object(Media,"text",new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
    t=Media(None,2,post)
    wordarray=t.text_
    assert(len(wordarray))==length

def test_stories_text_lettertrunicate3(mocker):
    length=TEXTLENGTH_DEFAULT
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    args_.getargs(["--letter-count"])
    mocker.patch('ofscraper.api.posts.config.read_config', return_value=migrationConfig)
    post=mocker.PropertyMock()
    post.post_media=["",""]
    mocker.patch.object(Media,"text",new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
    t=Media(None,2,post)
    wordarray=t.text_
    assert(len(wordarray))==len(f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")+2
  



def test_stories_text_lettertrunicate4(mocker):
    length=TEXTLENGTH_ALT2
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    args_.getargs(["--letter-count"])
    mocker.patch('ofscraper.api.posts.config.read_config', return_value=migrationConfig)
    post=mocker.PropertyMock()
    post.post_media=[]
    mocker.patch.object(Media,"text",new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
    t=Media(None,0,post)
    wordarray=t.text_
    assert(len(wordarray))==length
   

def test_stories_text_lettertrunicate5(mocker):
    length=int(TEXTLENGTH_ALT2/2)
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    args_.getargs(["--letter-count"])
    mocker.patch('ofscraper.api.posts.config.read_config', return_value=migrationConfig)
    post=mocker.PropertyMock()
    post.post_media=[]
    mocker.patch.object(Media,"text",new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
    t=Media(None,0,post)
    wordarray=t.text_
    assert(len(wordarray))==length

def test_stories_text_lettertrunicate6(mocker):
    length=TEXTLENGTH_DEFAULT
    migrationConfig={
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT
    }
    args_.getargs(["--letter-count"])
    mocker.patch('ofscraper.api.posts.config.read_config', return_value=migrationConfig)
    post=mocker.PropertyMock()
    post.post_media=[]
    mocker.patch.object(Media,"text",new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
    t=Media(None,0,post)
    wordarray=t.text_
    assert(len(wordarray))>=len("{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}")
  