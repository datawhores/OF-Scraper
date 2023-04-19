class Post():
    def __init__(self, post,model_id,username,responsetype=None):
        self._post=post
        self._model_id=model_id
        self._username=username
        self._responsetype=responsetype
    
     
    @property
    def allmedia(self):
        if self.responsetype=="highlights":
            return [{"url":self.post["cover"]}]
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
        return self._post.get("text")
 
    def title(self):
        return self._post.get("title")

    

    @property
    def responsetype(self):
        if self._responsetype:
            return self._responsetype
        if self.archived:
            return "achived"
        elif self._post.get("responseType")=="post":
            return "posts"
        return self._post.get("responseType")


    @property
    def id(self):
        return self._post["id"]


    @property
    def date(self):
        return self._post.get("createdAt") or self._post.get("postedAt")
    @property
    def value(self):
        return "free" if self.post.get("price")==0 else "paid"
    @property
    def price(self):
        return self.post.get('price') or 0

    @property
    def paid(self):
        if(self.post.get("isOpen") or self.post.get("isOpened")  or len(self.media)>0 or self.price!=0):
            return True
        return False
    @property
    def fromuser(self):
        if self._post.get("fromUser"):
            return self._post["fromUser"]["id"]
        else:
            return self._model_id
     


    @property
    def preview(self):
        return self._post.get("preview")


    @property
    def media(self):
        if (self.fromuser!=self.model_id):
            return []
        else:
            media=map(lambda x:Media(x[1],x[0],self),enumerate(self.allmedia))
            return list(filter(lambda x:x.canview==True,media))

    @responsetype.setter
    def _setresponsetype(self,responsetype):
        self.responsetype=responsetype
 




class Media():
    def __init__(self,media,count,post):
        self._media=media
        self._count=count
        self._post=post

    @property
    def mediatype(self):
        if self._media["type"]=="gif" or self._media["type"]=="photo":
            return "images"
        else:
            return f"{self._media['type']}s"
    
    @property
    def url(self):
        return self._media.get("source",{}).get("source")
    @property
    def post(self):
        return self._post



    @property
    def id(self):
        return self._media["id"]
    

    @property
    def canview(self):
        if self.responsetype=="highlights":
            return True
        return self._media.get("canView") or False
    @property
    def responsetype(self):
        return self._post.responsetype
    @property
    def value(self):
        return self._post.value
       
    @property
    def postdate(self):
        return self._post.date
    @property
    def date(self):
        return self._media.get("createdAt") or self._media.get("postedAt") or self.postdate
    @property
    def id(self):
        return self._media["id"]
    @property
    def postid(self):
        return self._post.id
    
    @property
    def text(self):
        return self._post.text
    @property
    def count(self):
        return self._count
    @property
    def filename(self):
        if not self.url:
            return
        return self.url.split('.')[-2].split('/')[-1].strip("/,.;!_-@#$%^&*()+\\ ")
    @property
    def preview(self):
       if self.post.preview:
           return 1
       else:
            return 1

    @property
    def linked(self):
        return None