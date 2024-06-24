import logging
import pathlib
import re
import subprocess
import time
import traceback

import ofscraper.utils.console as console_

console = console_.get_shared_console()
homeDir = pathlib.Path.home()
log = logging.getLogger("shared")


def ffmpegchecker(x):
    return ffmpegexecutecheck(x) and ffmpegpathcheck(x)


def ffmpegpathcheck(x):
    if not pathlib.Path(x).is_file():
        log.error(f"path to ffmpeg is not valid :{x}")
        return False
    return True


def ffmpegexecutecheck(x):
    try:
        t = subprocess.run([x], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if (
            re.search("ffmpeg", t.stdout.decode()) is not None
            or re.search("ffmpeg", t.stderr.decode()) is not None
        ):
            return True
    except Exception as E:
        log.error(f"issue executing path as ffmpeg: {x}")
        log.error(E)
        log.error(traceback.format_exc())
        time.sleep(2)
        return False
