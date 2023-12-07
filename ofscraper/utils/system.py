import asyncio
import json
import multiprocessing
import os
import platform
import subprocess
import sys

import psutil


def is_frozen():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return True
    else:
        return False


def get_parent():
    return (
        multiprocessing.parent_process() != None or "pytest" in sys.modules
    ) == False


def getcpu_count():
    if platform.system() != "Darwin":
        return len(psutil.Process().cpu_affinity())
    else:
        return psutil.cpu_count()


def speed_test():
    r = subprocess.Popen(
        ["speedtest-cli", "--bytes", "--no-upload", "--json", "--secure"],
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )
    out = ""
    for stdout_line in iter(r.stdout.readline, ""):
        out = out + stdout_line
    r.wait()
    speed = json.loads(out.strip())["download"]
    return speed


def getOpenFiles(unique=True):
    match = set()
    out = []
    for proc in psutil.process_iter():
        for ele in proc.open_files():
            if not unique:
                out.append(ele)
            elif ele.fd not in match:
                out.append(ele)
                match.add(ele.fd)
    return out


def set_mulitproc_start_type():
    plat = platform.system()
    if plat == "Darwin":
        multiprocessing.set_start_method("spawn")
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
        os.environ["no_proxy"] = "*"
    elif plat == "Windows":
        multiprocessing.set_start_method("spawn")
    else:
        multiprocessing.set_start_method("forkserver")


def set_eventloop():
    plat = platform.system()
    if plat == "Linux":
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
