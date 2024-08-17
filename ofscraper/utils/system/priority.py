import os
import platform
import psutil


def setpriority():
    os_used = platform.system()
    process = psutil.Process(
        os.getpid()
    )  # Set highest priority for the python script for the CPU
    if os_used == "Windows":  # Windows (either 32-bit or 64-bit)
        process.ionice(psutil.IOPRIO_NORMAL)
        process.nice(psutil.NORMAL_PRIORITY_CLASS)

    elif os_used == "Linux":  # linux
        process.ionice(psutil.IOPRIO_CLASS_BE)
        process.nice(0)
    else:  # MAC OS X or other
        process.nice(0)
