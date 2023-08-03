import platform
import psutil
def getcpu_count():
    if platform.system() != 'Darwin':      
        return len(psutil.Process().cpu_affinity())
    else:
        return psutil.cpu_count()