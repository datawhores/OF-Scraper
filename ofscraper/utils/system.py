import sys
import platform
import psutil
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