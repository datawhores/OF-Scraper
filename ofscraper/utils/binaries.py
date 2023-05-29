import json
import pathlib
import logging
import tempfile
import platform
import httpx
from rich.console import Console
import ofscraper.constants as constants
import ofscraper.prompts.prompts as prompts 
import ofscraper.utils.binaries as binaries

def mp4decrypt_download():
    bin_folder=pathlib.Path.home() / constants.configPath / "bin"
    if platform.system() == 'Windows':
        return mp4_decrypt_windows()
    else:
        return mp4_decrypt_linux()
 
def mp4_decrypt_windows():
    with tempfile.TemporaryDirectory() as t:
        zip_path=pathlib.Path(t,"mp4decrypt.zip")
        with httpx.stream("GET",constants.MP4DECRYPT_WINDOWS,timeout=None) as r:
                with open(pathlib.Path(zip_path,"wb")) as f:
                    for chunk in r.iter_bytes(chunk_size=1024):
                        f.write(chunk)
        print("test")

def mp4_decrypt_linux():
    with tempfile.TemporaryDirectory() as t:
        zip_path=pathlib.Path(t,"mp4decrypt.zip")
        with httpx.stream("GET",constants.MP4DECRYPT_LINUX,timeout=None) as r:
                with open(pathlib.Path(zip_path,"wb")) as f:
                    for chunk in r.iter_bytes(chunk_size=1024):
                        f.write(chunk)
                        
        print("test")