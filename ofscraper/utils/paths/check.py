import logging
import pathlib
import re
import subprocess
import time
import traceback
from contextlib import contextmanager

import ofscraper.utils.console as console_

console = console_.get_shared_console()
homeDir = pathlib.Path.home()
log = logging.getLogger("shared")


def mp4decryptchecker(x):
    return mp4decryptpathcheck(x) and mp4decryptexecutecheck(x)


def mp4decryptpathcheck(x):
    if not pathlib.Path(x).is_file():
        log.error("path to mp4decrypt is not valid")
        return False
    return True


def mp4decryptexecutecheck(x):
    try:
        t = subprocess.run([x], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if (
            re.search("mp4decrypt", t.stdout.decode()) != None
            or re.search("mp4decrypt", t.stderr.decode()) != None
        ):
            return True
    except Exception as E:
        log.error("issue executing path as mp4decrypt")
        log.error(E)
        log.error(traceback.format_exc())
        time.sleep(2)
        return False


def ffmpegchecker(x):
    return ffmpegexecutecheck(x) and ffmpegpathcheck(x)


def ffmpegpathcheck(x):
    if not pathlib.Path(x).is_file():
        log.error("path to ffmpeg is not valid")
        return False
    return True


def ffmpegexecutecheck(x):
    try:
        t = subprocess.run([x], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if (
            re.search("ffmpeg", t.stdout.decode()) != None
            or re.search("ffmpeg", t.stderr.decode()) != None
        ):
            return True
    except Exception as E:
        log.error("issue executing path as ffmpeg")
        log.error(E)
        log.error(traceback.format_exc())
        time.sleep(2)
        return False
