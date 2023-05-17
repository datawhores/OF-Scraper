import json
from prompt_toolkit.validation import Validator
import re
import string
from pathvalidate import  validate_filepath,validate_filename
import platform
import pathlib
import arrow
import textwrap
import src.utils.paths as paths
def emptyListValidator():
    def callable(x):
        return len(x)>0
    return Validator.from_callable(
    callable,
    "You must select at least one"
    )

def cleanTextInput(x):
    return x.strip()





def jsonValidator():
    def callable(x):
        try:
            json.loads(x)
            return True
        except:
            return False
    return Validator.from_callable(
                callable,
                "Invalid JSON syntax",
                move_cursor_to_end=True,
            )
def jsonloader(x):
    return json.loads(x)

def namevalitator():
    def callable(x):
       validchars=re.search("[a-zA-Z0-9_]*",x)
       return validchars!=None and len(x)==len(validchars.group(0))
    
    return Validator.from_callable(
                callable,
                "ONLY letters, numbers, and underscores are allowed",
                move_cursor_to_end=True,
            )


def dirformatvalidator():
    def callable(x):
        try:
            placeholders=list(filter(lambda x:x!=None,[v[1] for v in string.Formatter().parse(x)]))
            validplaceholders=set(["date","responsetype","mediatype","value","model_id","first_letter","sitename","model_username"])
            if len(list(filter(lambda x:x not in validplaceholders,placeholders)))>0:
                return False
            result={}

            for d in list(map(lambda x:{x:"placeholder"},placeholders)):
                result.update(d)
            validate_filepath(str(pathlib.Path(x.format(**result))),platform=platform.system())

            return True
        except:
            return False
      
    
    return Validator.from_callable(
                callable,
textwrap.dedent(f"""
Improper syntax or invalid placeholder
""").strip()                
                ,
                move_cursor_to_end=True,
            )

def fileformatvalidator():
    def callable(x):
        try:
            placeholders=list(filter(lambda x:x!=None,[v[1] for v in string.Formatter().parse(x)]))
            validplaceholders=set(["date","responsetype","mediatype","model_id",
                                   "first_letter","sitename","model_username","post_id","filename","value","text","ext"])
            
            if len(list(filter(lambda x:x not in validplaceholders,placeholders)))>0:
                return False
            result={}

            for d in list(map(lambda x:{x:"placeholder"},placeholders)):
                result.update(d)
            validate_filename(x.format(**result),platform=platform.system())

            return True
        except:
            return False
      
    
    return Validator.from_callable(
                callable,
textwrap.dedent(f"""
Improper syntax or invalid placeholder
""").strip()
                
                ,
                move_cursor_to_end=True,
            )

def dateplaceholdervalidator():
    def callable(x):
        try:
            if arrow.utcnow().format(x)==x:
                return False
            return True
        except:
            return False
    return Validator.from_callable(
                callable,
                """
    Date Format is invalid -> https://arrow.readthedocs.io/en/latest/guide.html#supported-tokens
                """
                ,True
    )


def mp4decryptvalidator():
    def callable(x):
       return paths.mp4decryptchecker(x)
            
    return Validator.from_callable(
                callable,
textwrap.dedent(f"""
Filepath is invalid or not detected as mp4decrypt
""").strip()
                
                ,
                move_cursor_to_end=True,
            )

def ffmpegvalidator():
    def callable(x):
       return paths.ffmpegchecker(x)
            
    return Validator.from_callable(
                callable,
textwrap.dedent(f"""
Filepath is invalid or not detected as ffmpeg
""").strip()
                
                ,
                move_cursor_to_end=True,
            )

def metadatavalidator():
    def callable(x):
        try:
            placeholders=list(filter(lambda x:x!=None,[v[1] for v in string.Formatter().parse(x)]))
            validplaceholders=set(["sitename","first_letter","model_username","model_id","configpath","profile"])
            if len(list(filter(lambda x:x not in validplaceholders,placeholders)))>0:
                return False
            result={}

            for d in list(map(lambda x:{x:"placeholder"},placeholders)):
                result.update(d)
            validate_filepath(str(pathlib.Path(x.format(**result))),platform=platform.system())

            return True
        except:
            return False
      
    
    return Validator.from_callable(
                callable,
textwrap.dedent(f"""
Improper syntax or invalid placeholder
""").strip()
                
                ,
                move_cursor_to_end=True,
            )
def DiscordValidator():
    def callable(x):
         if len(x)==0:
            return True
         return re.search("https://discord.com/api/webhooks/[0-9]*/[0-9a-z]*",x)!=None
    return Validator.from_callable(
    callable,
textwrap.dedent(    
"""
must be discord webhook -> example: https://discord.com/api/webhooks/{numeric}/{alphanumeric}
    """
    ).strip())