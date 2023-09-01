import sys
import json
import logging
import platform
import psutil
import subprocess
def is_frozen():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
       return True
    else:
        return False

def getcpu_count():
    if platform.system() != 'Darwin':      
        return len(psutil.Process().cpu_affinity())
    else:
        return psutil.cpu_count()

def speed_test():
    r=subprocess.Popen(["speedtest-cli","--bytes","--no-upload","--json","--secure"],stdout=subprocess.PIPE,universal_newlines=True)
    out=""
    for stdout_line in iter(r.stdout.readline, ""):
        out=out+stdout_line 
    r.wait()
    speed=json.loads(out.strip())["download"]
    return speed

