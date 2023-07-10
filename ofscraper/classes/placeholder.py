import logging
import pathlib
import ofscraper.utils.paths as paths
import ofscraper.utils.config as config_
import ofscraper.utils.profiles as profiles
import ofscraper.api.me as me
import arrow


log=logging.getLogger(__package__)
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

               "custom": config_.get_custom(config_.read_config()) }
        
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
            formatStr=eval("f'{}'".format(config_.get_metadata(config_.read_config())))
        else:
            formatStr=config_.get_metadata(config_.read_config()).format(       
                            **self._variables)

        return pathlib.Path(formatStr,"user_data.db")


 

    @wrapper
    def getmediadir(self,ele,username,model_id):
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
            downloadDir=eval("f'{}'".format(config_.get_dirformat(config_.read_config())))
        else:
            
            downloadDir=config_.get_dirformat(config_.read_config())\
            .format(**self._variables)
            
        return root /downloadDir  
    
    
    @wrapper
    def createfilename(self,ele,username,model_id,ext):
        filename=ele.filename_;self._variables.update({"filename":filename})
        file_name=ele.filename_;self._variables.update({"file_name":filename})
        if ele.responsetype_ =="profile":
            return f"{filename}.{ext}"
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
        download_type=ele.downloadtype;self._variables.update({"downloadtype":download_type})


        

       
        log.trace(f"modelid:{model_id}  filename placeholders {list(filter(lambda x:x[0] in set(list(self._variables.keys())),list(locals().items())))}")
      
        if config_.get_allow_code_execution(config_.read_config()):
            return eval("f'{}'".format(config_.get_fileformat(config_.read_config())))
        else:
            return config_.get_fileformat(config_.read_config()).format(**self._variables) 
