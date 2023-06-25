import re
import logging
import aiohttp
import arrow
from ..constants import LICENCE_URL
import ofscraper.utils.args as args_
import ofscraper.utils.auth as auth
from mpegdash.parser import MPEGDASHParser
import ofscraper.utils.config as config


log=logging.getLogger(__package__)

class Post():
    def __init__(self, post, model_id, username, responsetype=None):
        self._post = post
        self._model_id = int(model_id)
        self._username = username
        self._responsetype_ = responsetype or post.get("responseType")

    #All media return from API dict
    @property
    def post_media(self):
        if self._responsetype_ == "highlights":
            return [{"url": self.post["cover"], "type":"photo"}]
        return self._post.get("media") or []

    @property
    def post(self):
        return self._post

    @property
    def model_id(self):
        return self._model_id

    @property
    def username(self):
        return self._username

    @property
    def archived(self):
        if self.post.get("isArchived"):
            return 1
        return 0

    @property
    def text(self):
        if self._responsetype_ == "highlights":
            return self.post.get("title") 
        return self._post.get("text")

    @property
    def title(self):
        return self._post.get("title")

    # original responsetype for database
    @property
    def responsetype_(self):
        return self._responsetype_

    @property
    def responsetype(self):
        if self.archived:
            if config.get_archived_responsetype(config.read_config()) == "":
                return "achived"
            return config.get_archived_responsetype(config.read_config())

        else:
            response=config.read_config().get("responsetype", {}).get(self._responsetype_) 
            if  response == "":
                return self._responsetype_.capitalize()
            elif  response == None:
                return self._responsetype_.capitalize()
            elif  response != "":
                return  response.capitalize()

    @property
    def id(self):
        return self._post["id"]

    @property
    def date(self):
        return self._post.get("createdAt") or self._post.get("postedAt")
    #modify verison of post date
    @property
    def date_(self):
        return arrow.get(self.date).format("YYYY-MM-DD hh:mm:ss")

    @property
    def value(self):
        if self.price == 0:
            return "free"
        elif self.price > 0:
            return "paid"

    @property
    def price(self):
        return float(self.post.get('price') or 0)

    @property
    def paid(self):
        if (self.post.get("isOpen") or self.post.get("isOpened") or len(self.media) > 0 or self.price != 0):
            return True
        return False

    @property
    def fromuser(self):
        if self._post.get("fromUser"):
            return int(self._post["fromUser"]["id"])
        else:
            return self._model_id

    @property
    def preview(self):
        return self._post.get("preview")

    #media object array for media that is unlocked or viewable
    @property
    def media(self):
        if (int(self.fromuser) != int(self.model_id)):
            return []
        else:
            media = map(lambda x: Media(
                x[1], x[0], self), enumerate(self.post_media))
            return list(filter(lambda x: x.canview == True, media))
    #media object array for all media
    @property
    def all_media(self):
        return list(map(lambda x: Media(
            x[1], x[0], self), enumerate(self.post_media)))
    @property
    def expires(self):
        return (self._post.get("expiredAt",{}) or self._post.get("expiresAt",None))!=None
class Media():
    def __init__(self, media, count, post):
        self._media = media
        self._count = count
        self._post = post

    @property
    def expires(self):
        return self._post.expires

    @property
    def mediatype(self):
        if self.responsetype_ == "highlights":
            return "images"
        if self._media["type"] == "gif" or self._media["type"] == "photo":
            return "images"
        else:
            return f"{self._media['type']}s"
    @property
    def length(self):
        return self._media.get("duration") or self._media.get("source",{}).get("duration")
    @property
    def length_(self):
        if not self.length:
            return "N/A"
        return str((arrow.get(self.length)-arrow.get(0)))

   

      

    @property
    def url(self):
        if self.responsetype_ == "stories":
            return self._media.get("files", {}).get("source", {}).get("url")
        elif self.responsetype_ == "highlights":
            return self._media.get("url")
        elif self.responsetype_ == "profile":
            return self._media.get("url")
        else:
            return self._media.get("source", {}).get("source")
        



    @property
    def post(self):
        return self._post

    @property
    def id(self):
        return self._media["id"]

    # ID for use in dynamic names
    @property
    def postid_(self):
        if self.count != None and len(self._post.post_media) > 1:
            return f"{self._post._post['id']}_{self.count}"
        return self._post._post['id']

    @property
    def canview(self):
        if self.responsetype_ == "highlights":
            return True
        return self._media.get("canView") or True if (self.url or self.mpd)!=None else False

    @property
    def responsetype(self):
        return self._post.responsetype

    @property
    def responsetype_(self):
        return self._post.responsetype_

    @property
    def value(self):
        return self._post.value

    @property
    def postdate(self):
        return self._post.date
    #modified verison of post date
    @property
    def postdate_(self):
        return self._post.date_ 

    @property
    def date(self):
        return self._media.get("createdAt") or self._media.get("postedAt") or self.postdate
    
    #modified verison of media date
    @property
    def date_(self):
        if self._media.get("createdAt") or self._media.get("postedAt"):
            return arrow.get(self._media.get("createdAt") or self._media.get("postedAt")).format("YYYY-MM-DD hh:mm:ss")()
        return self.postdate_

 
    @property
    def id(self):
        return self._media.get("id")

    @property
    def postid(self):
        return self._post.id

    @property
    def text(self):
        return self._post.text

    
    @property
    def mpd(self):
        if self.url:
            return None
        return self._media.get("files",{}).get("drm",{}).get("manifest",{}).get("dash")
    @property
    def policy(self):
        if self.url:
            return None
        return self._media.get("files",{}).get("drm",{}).get("signature",{}).get("dash",{}).get("CloudFront-Policy")
    
    @property
    def keypair(self):
        if self.url:
            return None
        return self._media.get("files",{}).get("drm",{}).get("signature",{}).get("dash",{}).get("CloudFront-Key-Pair-Id")
    
    @property
    def signature(self):
        if self.url:
            return None
        return self._media.get("files",{}).get("drm",{}).get("signature",{}).get("dash",{}).get("CloudFront-Signature")
    

    @property
    def mpdout(self):
        if not self.mpd:
            return None



    @property
    def text_(self):
        if self.responsetype_!="Profile":
            text = self.text or self.filename or arrow.get(self.date).format(config.get_date(config.read_config()))
        elif self.responsetype_=="Profile":
            text=f"{arrow.get(self.date).format(config.get_date(config.read_config()))} {self.text or self.filename}"
        if len(text)==0:
            return text
        # this is for removing emojis
        # text=re.sub("[^\x00-\x7F]","",text)
        # this is for removing html tags
        text = re.sub("<[^>]*>", "", text)
        # this for remove random special invalid special characters
        text = re.sub('[\n<>:"/\|?*]+', '', text)
        text = re.sub(" +", " ", text)
        text=re.sub(" ",config.get_spacereplacer(config.read_config()),text)
        length = int(config.get_textlength(config.read_config()))
        if length==0 and self._addcount():
                return f"{text}_{self.count}"
        elif length==0 and not self._addcount():
                return text
 
        elif args_.getargs().letter_count:
            if not self._addcount():
                return "".join(list(text))[:length]
            elif self._addcount():
                append=f"_{self.count}"
                baselength=length-len(append)
                return f"{''.join(list(text)[:baselength])}{append}"         
        elif not args_.getargs().letter_count :
            # split and reduce
            wordarray=list(filter(lambda x:len(x)!=0,re.split("( )", text)))
            if not self._addcount():
                return "".join(wordarray[:length])
            elif self._addcount():
                append=f"_{self.count}"
                baselength=length-1
                splitArray=wordarray[:baselength]
                text=f"{''.join(splitArray)}{append}"
                return text

                



       
   
     
       

       

    @property
    def count(self):
        return self._count+1

    #og filename
    @property
    def filename(self):
        if not self.url and not self.mpd:
            return None
        elif not self.responsetype=="Profile":
            return re.sub("\.mpd$","",(self.url or self.mpd).split('.')[-2].split('/')[-1].strip("/,.;!_-@#$%^&*()+\\ "))
        else:
            filename= re.sub("\.mpd$","",(self.url or self.mpd).split('.')[-2].split('/')[-1].strip("/,.;!_-@#$%^&*()+\\ "))
            return f"{filename}_{arrow.get(self.date).format(config.get_date(config.read_config()))}"
    @property
    def filename_(self):
        if self.filename==None:
            return None
        if self.mediatype=="videos":
            return self.filename if re.search("_source",self.filename) else f"{self.filename}_source"
        return self.filename

            


    @property
    def preview(self):
        if self.post.preview:
            return 1
        else:
            return 0

    @property
    def linked(self):
        return None

    @property
    def media(self):
        return self._media
    @property
    async def parse_mpd(self): 
        if not self.mpd:
            return
      
        params={"Policy":self.policy,"Key-Pair-Id":self.keypair,"Signature":self.signature}
        async with aiohttp.ClientSession() as session:
            headers=auth.make_headers(auth.read_auth())
            headers=auth.create_sign(self.mpd, headers) 
            async with session.request("get",self.mpd,headers=headers,params=params) as r:
                if not r.ok:
                    return None
                return MPEGDASHParser.parse(await r.text())
    @property
    def license(self):
        if not self.mpd:
            return None
        responsetype=self.post.post["responseType"]
        if responsetype in ["timeline","archived","pinned"]:
            responsetype="post"
        return LICENCE_URL.format(self.id,responsetype,self.postid)


    # for use in dynamic names
    def _addcount(self):
        if len(self._post.post_media) > 1 or self.responsetype_ in ["stories", "highlights"]:
            return True
        return False
