from test.test_constants import *
import ofscraper.utils.args as args_
import ofscraper.utils.filters as filters
from ofscraper.api.posts import Post
import arrow
def test_after(mocker):
    username="test"
    model_id=TEST_ID
    input=list(map(lambda x:Post(x,model_id,username),POST_ARRAY))
    output=[]
    [ output.extend(ele.media) for ele in input]
    mocker.patch("ofscraper.utils.filters.args",new=args_.getargs(["--after","2023"]))
    media=filters.posts_date_filter(output)
    assert(len(list(filter(lambda x:arrow.get(x.postdate).year==2023,media))))==len(media)



def test_after2(mocker):
    username="test"
    model_id=TEST_ID
    input=list(map(lambda x:Post(x,model_id,username),POST_ARRAY))
    output=[]
    [ output.extend(ele.media) for ele in input]
    mocker.patch("ofscraper.utils.filters.args",new=args_.getargs(["--after","2023"]))
    media=filters.posts_date_filter(output)
    assert(len(list(filter(lambda x:arrow.get(x.postdate).year!=2023,media))))==0



def test_before(mocker):
    username="test"
    model_id=TEST_ID
    input=list(map(lambda x:Post(x,model_id,username),POST_ARRAY))
    output=[]
    [ output.extend(ele.media) for ele in input]
    mocker.patch("ofscraper.utils.filters.args",new=args_.getargs(["--before","2023"]))
    media=filters.posts_date_filter(output)
    assert(len(list(filter(lambda x:arrow.get(x.postdate).year!=2023,media))))==len(media)



def test_before2(mocker):
    username="test"
    model_id=TEST_ID
    input=list(map(lambda x:Post(x,model_id,username),POST_ARRAY))
    output=[]
    [ output.extend(ele.media) for ele in input]
    mocker.patch("ofscraper.utils.filters.args",new=args_.getargs(["--before","2023"]))
    media=filters.posts_date_filter(output)
    assert(len(list(filter(lambda x:arrow.get(x.postdate).year==2023,media))))==0


   