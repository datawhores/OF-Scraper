import sys
import json
import platform
import psutil
import subprocess
import multiprocessing
def is_frozen():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
       return True
    else:
        return False

def get_parent():
    return (multiprocessing.parent_process()!=None or "pytest" in sys.modules)==False
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

def getOpenFiles(unique=True):
    match=set()
    out=[]
    for proc in psutil.process_iter():
        for ele in proc.open_files():
            if not unique:
                out.append(ele)
            elif ele.fd not in match:
                out.append(ele)
                match.add(ele.fd)
    return out

