r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import hashlib
import re
import json
import time
import logging
from urllib.parse import urlparse
import requests
from rich.console import Console

import browser_cookie3
from tenacity import retry,stop_after_attempt,retry_if_not_exception_type,wait_fixed

import ofscraper.prompts.prompts as prompts
from ..constants import configPath, DIGITALCRIMINALS, requestAuth,DEVIINT
import ofscraper.utils.paths as paths
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.profiles as profiles
import ofscraper.utils.args as args_
import ofscraper.utils.config as config
import ofscraper.constants as constants


console=Console()
log=logging.getLogger("shared")

def read_auth():
    authFile=paths.get_auth_file()

    while True:
        try:
            with open(authFile, 'r') as f:
                authText=f.read()
                auth = json.loads(authText)
                for key in list(filter(lambda x:x!="auth_uid_",auth.keys())):
                    if auth[key]==None or  auth[key]=="":
                        console.print("Auth Value not set retriving missing values")
                        make_auth()
                        break
            break
        except FileNotFoundError:
            console.print(
                "You don't seem to have an `auth.json` file")
            make_auth()
        except json.JSONDecodeError as e:
            print("Your auth.json has a syntax error")
            print(f"{e}\n\n")
            if prompts.reset_auth_prompt():
                with open( authFile, 'w') as f:
                    f.write(prompts.manual_auth_prompt(authText))
            else:
                with open(authFile,"w") as f: 
                    f.write(json.dumps(get_empty()))


    make_request_auth()       
    return auth

def get_empty():
    return{
            'auth': {
                'app-token': '33d57ade8c02dbc5a333db99ff9ae26a',
                'sess': '',
                'auth_id': '',
                'auth_uid_': '',
                'user_agent': '',
                'x-bc': ''
            }
        }


def edit_auth():
    authFile=paths.get_auth_file()
    log.info(f"Auth Path {authFile}" )
    try:
        with open(authFile, 'r') as f:
            authText=f.read()
            auth = json.loads(authText)
        print("Hint: Select 'Enter Each Field Manually' to edit your current config\n")
        make_auth(auth)

        console.print('Your `auth.json` file has been edited.')
    except FileNotFoundError:
        
        if prompts.ask_make_auth_prompt():
            make_auth()
    except json.JSONDecodeError as e:
            while True:
                try:
                    print("Your auth.json has a syntax error")
                    if prompts.reset_auth_prompt()=="Reset Default":
                        make_auth()
                    else:
                        with open( authFile, 'w') as f:
                            f.write(prompts.manual_auth_prompt(authText))

                    with open(authFile, 'r') as f:
                        authText=f.read()
                        auth = json.loads(authText)
                    break
                except Exception as E:
                    continue
    make_request_auth() 

def make_auth( auth=None):
    authFile=paths.get_auth_file()
    defaultAuth=  get_empty()

    browserSelect=prompts.browser_prompt()

    auth= auth or defaultAuth
    if  browserSelect!="Enter Each Field Manually" and browserSelect!="Paste From M-rcus\' OnlyFans-Cookie-Helper":
        temp=requests.utils.dict_from_cookiejar(getattr(browser_cookie3, browserSelect.lower())(domain_name="onlyfans"))
        auth=auth or  defaultAuth
        for key in ["sess","auth_id","auth_uid_"]:
            auth["auth"][key]=temp.get(key,"")
        console.print("You'll need to go to onlyfans.com and retrive header information\nGo to https://github.com/datawhores/OF-Scraper and find the section named 'Getting Your Auth Info'\nCookie information has been retived automatically\nSo You only need to retrive the x-bc header and the user-agent",style="yellow")
        if not auth["auth"].get("x-bc"):
            auth["auth"]["x-bc"]=prompts.xbc_prompt()
        auth["auth"]["user_agent"]= prompts.user_agent_prompt(auth["auth"].get("user_agent") or "")


 
    elif browserSelect=="Paste From M-rcus\' OnlyFans-Cookie-Helper":
        auth=prompts.auth_full_paste()
        auth["auth"]["app-token"]="33d57ade8c02dbc5a333db99ff9ae26a"
        for key in ["username","support_2fa","active","email","password","hashed"]:
            auth["auth"].pop(key)
        auth["auth"]["x-bc"]=auth["auth"].pop("x_bc").strip()
        tempCookie=auth["auth"].pop("cookie")
        for ele in tempCookie.split(";"):
            if ele.find("auth_id")!=-1:
                auth["auth"]["auth_id"]=ele.replace("auth_id=","")
            elif ele.find("sess")!=-1:
                auth["auth"]["sess"]=ele.replace("sess=","")
            elif ele.find("auth_uid")!=-1:
                auth["auth"]["auth_uid_"]=ele.replace("auth_uid_","").replace("=","")



    else:
        console.print("You'll need to go to onlyfans.com and retrive header information\nGo to https://github.com/datawhores/OF-Scraper and find the section named 'Getting Your Auth Info'\nYou only need to retrive the x-bc header,the user-agent, and cookie information",style="yellow")
        auth['auth'].update(prompts.auth_prompt(auth['auth']))
    for key,item in auth["auth"].items():
        newitem=item.strip()
        newitem=re.sub("^ +","",newitem)
        newitem=re.sub(" +$","",newitem)
        newitem=re.sub("\n+","",newitem)
        auth["auth"][key]=newitem
    console.print(f"{auth}\nWriting to {authFile}",style="yellow")
    with open(authFile, 'w') as f:
        f.write(json.dumps(auth, indent=4))





def make_headers(auth):
    headers = {
        'accept': 'application/json, text/plain, */*',
        'app-token': auth['auth']['app-token'],
        'user-id': auth['auth']['auth_id'],
        'x-bc': auth['auth']['x-bc'],
        'referer': 'https://onlyfans.com',
        'user-agent': auth['auth']['user_agent'],
    }
    return headers



def add_cookies():

    authFile=paths.get_auth_file()
    with open(authFile, 'r') as f:
        auth = json.load(f)

    cookies={}
    cookies.update({"sess": auth['auth']['sess']})
    cookies.update({"auth_id": auth['auth']['auth_id']})

    if auth['auth']['auth_uid_']:
        cookies.update({"auth_uid_":  auth['auth']['auth_uid_']})

    return cookies
def get_cookies():
    authFile=paths.get_auth_file()

    with open( authFile, 'r') as f:
        auth = json.load(f)
    return  f"auth_id={auth['auth']['auth_id']};sess={auth['auth']['sess']};"

def create_sign(link, headers):
    """
    credit: DC and hippothon
    """
    content = read_request_auth()

    time2 = str(round(time.time() * 1000))

    path = urlparse(link).path
    query = urlparse(link).query
    path = path if not query else f"{path}?{query}"

    static_param = content['static_param']

    a = [static_param, time2, path, headers['user-id']]
    msg = "\n".join(a)

    message = msg.encode("utf-8")
    hash_object = hashlib.sha1(message)
    sha_1_sign = hash_object.hexdigest()
    sha_1_b = sha_1_sign.encode("ascii")

    checksum_indexes = content['checksum_indexes']
    checksum_constant = content['checksum_constant']
    checksum = sum(sha_1_b[i] for i in checksum_indexes) + checksum_constant

    final_sign = content['format'].format(sha_1_sign, abs(checksum))


    headers.update(
        {
            'sign': final_sign,
            'time': time2
        }
    )
    return headers


def read_request_auth() -> dict:
    profile = profiles.get_active_profile()
    

    p = paths.get_config_home()/profile/ requestAuth
    with open(p, 'r') as f:
        content = json.load(f)
    return content


def make_request_auth():
    request_auth = {
        'static_param': '',
        'format': '',
        'checksum_indexes': [],
        'checksum_constant': 0
    }

    # *values, = get_request_auth()
    result = get_request_auth()
    if result:
        *values, = result

        request_auth.update(zip(request_auth.keys(), values))

        profile = profiles.get_active_profile()

        p = paths.get_config_home()/profile
        if not p.is_dir():
            p.mkdir(parents=True, exist_ok=True)

        with open(p / requestAuth, 'w') as f:
            f.write(json.dumps(request_auth, indent=4))





def get_request_auth():
    if (args_.getargs().dynamic_rules or config.get_dynamic(config.read_config()) or "deviint")=="deviint":
        return get_request_auth_deviint()
    else:
        return get_request_digitalcriminals()

@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_fixed(8))
def get_request_auth_deviint():
    with sessionbuilder.sessionBuilder(backend="httpx",set_header=False,set_cookies=False,set_sign=False) as c:
        with c.requests(DEVIINT)() as r:
            if r.ok:
                content = r.json_()
                static_param = content['static_param']
                fmt = f"{content['start']}:{{}}:{{:x}}:{content['end']}" 
                checksum_indexes = content['checksum_indexes']
                checksum_constant = content['checksum_constant']
                return (static_param, fmt, checksum_indexes, checksum_constant)
            else:
               r.raise_for_status()  
@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_fixed(8))  
def get_request_digitalcriminals():
   with sessionbuilder.sessionBuilder(backend="httpx",set_header=False,set_cookies=False,set_sign=False) as c:
        with c.requests(DIGITALCRIMINALS)() as r:
            if r.ok:
                content = r.json_()
                static_param = content['static_param']
                fmt = content['format']
                checksum_indexes = content['checksum_indexes']
                checksum_constant = content['checksum_constant']
                return (static_param, fmt, checksum_indexes, checksum_constant)
            else:
                r.raise_for_status() 
