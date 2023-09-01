import logging
import os
import re
import pathlib
import ofscraper.utils.paths as paths
import ofscraper.utils.config as config_
import ofscraper.utils.profiles as profiles
import ofscraper.api.me as me
import arrow
from diskcache import Cache



log=logging.getLogger("shared")
class Placeholders:
    def __init__(self) -> None:
        None

    def wrapper(f):
        def wrapper(*args):
            args[0]._variables={}
            args[0].create_variables()
            return f(args[0],*args[1:])
        return wrapper
    def create_variables(self):
        my_profile=profiles.get_my_info()
        my_id, my_username =me.parse_user(my_profile)
        self._variables={"configpath":paths.get_config_home(),
               "profile":profiles.get_active_profile(),
               "sitename":"Onlyfans",
               "site_name":"Onlyfans",
               "save_location":config_.get_save_location(config_.read_config()),
               "my_id":my_id,
               "my_username":my_username,
               "root": pathlib.Path((config_.get_save_location(config_.read_config()))),
               "customval": config_.get_custom(config_.read_config()) }
        
        globals().update(self._variables)
    @wrapper
    def databasePathHelper(self,model_id,model_username):
        username=model_username;self._variables.update({"username":username})
        modelusername=model_username;self._variables.update({"modelusername":modelusername})
        model_username=model_username;self._variables.update({"model_username":model_username})
        first_letter=username[0].capitalize();self._variables.update({"first_letter":first_letter})
        firstletter=username[0].capitalize();self._variables.update({"firstletter":firstletter})
        self._variables.update({"model_id":model_id})
        modelid=model_id;self._variables.update({"modelid":modelid})

        log.trace(f"modelid:{model_id}  database placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}")
        if config_.get_allow_code_execution(config_.read_config()):
            if isinstance(customval,dict)==False:
                    try:custom=eval(customval)
                    except:custom={}
            else:
                    custom={}
                    for key,val in customval.items():
                        try:custom[key]=eval(val)
                        except:custom[key]=val
   
            formatStr=eval("f'{}'".format(config_.get_metadata(config_.read_config())))
            
        else:
            formatStr=config_.get_metadata(config_.read_config()).format(       
                          **self._variables)
        data_path=pathlib.Path(formatStr,'user_data.db')
        data_path=os.path.normpath(data_path )
        log.trace(f"final database path {data_path}")
        return pathlib.Path(data_path)


    def databasePathCopyHelper(self,model_id,model_username):
        cache = Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
        counter= (cache.get(f"{model_username}_{model_id}_dbcounter",0)%5)+1
        cache.set(f"{model_username}_{model_id}_dbcounter",counter)
        cache.close()
        return pathlib.Path(re.sub('user_data.db',f"/backup/user_data_copy_{counter}.db",str(self.databasePathHelper(model_id,model_username))))

  


    @wrapper
    def getmediadir(self,ele,username,model_id):

        
        root=pathlib.Path(config_.get_save_location(config_.read_config()))
        self._variables.update({"username":username})
        self._variables.update({"model_id":model_id})
        user_name=username;self._variables.update({"user_name":username})
        modelid=model_id;self._variables.update({"modelid":modelid})
        post_id=ele.postid_;self._variables.update({"post_id":post_id})
        postid=ele.postid_;self._variables.update({"postid":postid})
        media_id=ele.id;self._variables.update({"media_id":media_id})
        mediaid=ele.id;self._variables.update({"mediaid":mediaid})
        first_letter=username[0].capitalize();self._variables.update({"first_letter":first_letter})
        firstletter=username[0].capitalize();self._variables.update({"firstletter":firstletter})
        mediatype=ele.mediatype.capitalize();self._variables.update({"mediatype":mediatype})
        media_type=ele.mediatype.capitalize();self._variables.update({"media_type":media_type})
        value=ele.value.capitalize();self._variables.update({"value":value})
        date=arrow.get(ele.postdate).format(config_.get_date(config_.read_config())) \
        ;self._variables.update({"date":date})
        model_username=username; \
        self._variables.update({"model_username":username})
        modelusername=username; \
        self._variables.update({"modelusername":username})
        responsetype=ele.responsetype;self._variables.update({"responsetype":responsetype})
        response_type=ele.responsetype;self._variables.update({"response_type":response_type})

        label=ele.label_;self._variables.update({"label":label})
        downloadtype=ele.downloadtype;self._variables.update({"downloadtype":downloadtype})
        download_type=ele.downloadtype;self._variables.update({"download_type":download_type})

        log.trace(f"modelid:{model_id}  mediadir placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}")
        if config_.get_allow_code_execution(config_.read_config()):
            if isinstance(customval,dict)==False:
                    try:custom=eval(customval)
                    except:custom={}
            else:
                    custom={}
                    for key,val in customval.items():
                        try:custom[key]=eval(val)
                        except:custom[key]=val
            downloadDir=eval("f'{}'".format(config_.get_dirformat(config_.read_config())))
        else:
            
            downloadDir=config_.get_dirformat(config_.read_config())\
            .format(**self._variables)
        final_path=pathlib.Path(os.path.normpath(root /downloadDir ))
        log.trace(f"final mediadir path {final_path}")
        return final_path
    
    
    @wrapper
    def createfilename(self,ele,username,model_id,ext):
        filename=ele.filename_;self._variables.update({"filename":filename})
        file_name=ele.filename_;self._variables.update({"file_name":file_name})
        self._variables.update({"username":username})
        self._variables.update({"model_id":model_id})
        self._variables.update({"ext":ext})

        user_name=username;self._variables.update({"user_name":username})
        modelid=model_id;self._variables.update({"modelid":modelid})
        post_id=ele.postid_;self._variables.update({"post_id":post_id})
        postid=ele.postid_;self._variables.update({"postid":postid})
        media_id=ele.id;self._variables.update({"media_id":media_id})
        mediaid=ele.id;self._variables.update({"mediaid":mediaid})
        first_letter=username[0].capitalize();self._variables.update({"first_letter":first_letter})
        firstletter=username[0].capitalize();self._variables.update({"firstletter":firstletter})
        mediatype=ele.mediatype.capitalize();self._variables.update({"mediatype":mediatype})
        media_type=ele.mediatype.capitalize();self._variables.update({"media_type":media_type})
        value=ele.value.capitalize();self._variables.update({"value":value})
        date=arrow.get(ele.postdate).format(config_.get_date(config_.read_config())) \
        ;self._variables.update({"date":date})
        model_username=username; \
        self._variables.update({"model_username":username})
        modelusername=username; \
        self._variables.update({"modelusername":username})
        responsetype=ele.responsetype;self._variables.update({"responsetype":responsetype})
        response_type=ele.responsetype;self._variables.update({"response_type":response_type})

        label=ele.label_;self._variables.update({"label":label})
     
        text=ele.text_;self._variables.update({"text":text})
        downloadtype=ele.downloadtype;self._variables.update({"downloadtype":downloadtype})
        download_type=ele.downloadtype;self._variables.update({"download_type":download_type})

        log.trace(f"modelid:{model_id}  filename placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}")
        out=None
        if config_.get_allow_code_execution(config_.read_config()):
            if isinstance(customval,dict)==False:
                    try:custom=eval(customval)
                    except:custom={}
            else:
                    custom={}
                    for key,val in customval.items():
                        try:custom[key]=eval(val)
                        except:custom[key]=val
            out=eval('f"""{}"""'.format(config_.get_fileformat(config_.read_config())))
        else:
            if ele.responsetype_ =="profile":out=f"{filename}.{ext}"
            else:out=config_.get_fileformat(config_.read_config()).format(**self._variables) 
        log.trace(f"final filename path {out}")
        return out
        
        
 







       


# def all_placeholders():
#       {"user_name","modelid","model_id","username","postid","postid","media_id",
#        "mediaid","first_letter","firstletter","mediatype","media_type","value","date",
#        "model_username","modelusername","response_type","responsetype","label","downloadtype","download_type"}
   


    