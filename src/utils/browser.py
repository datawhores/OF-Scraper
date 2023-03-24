import subprocess
import platform
import re
from bs4 import BeautifulSoup
def getuseragent(browser):
    try:

        if browser.lower()=="chrome":
            if platform.system()=="Linux":
                html=subprocess.run(["google-chrome" ,"--headless=new", "--dump-dom", "http://whatsmyuseragent.org/"],stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
                return re.sub("Headlesschrome","Chrome",BeautifulSoup(html, 'html.parser').find(class_="intro-text").text,flags=re.IGNORECASE)
    except:
        return None

