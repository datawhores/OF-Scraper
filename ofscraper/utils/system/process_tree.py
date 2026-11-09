"""Keep track of every program a command starts, so they can all be stopped.

A command (a user script, ffmpeg) can start programs of its own. When the
command exits or is killed, those programs are left running unless something
stops them. ProcessTree puts the command and everything it starts into one
group the operating system tracks:

- POSIX: a new session, so the command leads its own process group and its
  children join it. A program that starts its own session (for example with
  `setsid`) leaves the group and isn't stopped. Because the command is no
  longer in the terminal's process group, Ctrl+C doesn't reach it; groups
  still running when ofscraper exits are killed then (see _kill_at_exit).
- Windows: a Job Object. The command starts suspended and is resumed once it
  is in the job, so everything it starts is in the job too (a venv's
  python.exe starts the real interpreter as a child at once). Programs can't
  leave the job, and it is created with KILL_ON_JOB_CLOSE, so its programs
  are also killed when ofscraper exits, however it exits.
"""

import asyncio
import atexit
import os
import signal
import sys

import psutil

STOP_WAIT = 2  # seconds a program gets to exit after it is asked to stop
STOP_POLL = 0.05  # seconds between checks that the programs have exited

# POSIX process groups not yet stopped, to kill if ofscraper exits first
# (Ctrl+C leaves running tasks unfinished). Only the process that started
# them kills them: a forked child inherits the set but not the groups.
_live_groups = set()
_owner_pid = os.getpid()


class ProcessTree:
    """The programs a command starts. Use as a context manager around the
    command's lifetime: pass popen_kwargs() when starting it, attach() it
    once started, then stop() what is left once it has exited."""

    def __init__(self):
        self._pgid = None
        self._job = None
        # POSIX: True once the group is known to be empty or has been killed.
        self._settled = False

    def popen_kwargs(self, kwargs):
        """kwargs for starting the command, with what tracking needs added."""
        if sys.platform == "win32":
            flags = kwargs.get("creationflags", 0) | _CREATE_SUSPENDED
            return {**kwargs, "creationflags": flags}
        return {**kwargs, "start_new_session": True}

    def attach(self, pid):
        """Start tracking the command, which was started with popen_kwargs().

        Returns None, or the OSError that kept the programs from being
        tracked; the command runs either way. Raises OSError if the command
        (started suspended on Windows) couldn't be resumed: kill it then.
        """
        if sys.platform == "win32":
            self._job, error = _windows_attach(pid)
            return error
        # With start_new_session the command leads its own process group.
        self._pgid = pid
        _live_groups.add(pid)
        return None

    async def running(self):
        """Whether any program in the tree is still running."""
        if self._job is not None:
            return _windows_job_active(self._job)
        if self._pgid is None:
            return False
        if not _signal_group(self._pgid, 0):
            # The usual case: the group is empty, which the signal settles.
            self._settled = True
            return False
        # A program that exited but wasn't reaped (a zombie) stays in the
        # group: in Docker, ofscraper is PID 1 and inherits orphans it never
        # reaps. Look for a live member, off the event loop: it scans every
        # process.
        if await asyncio.to_thread(_live_member, self._pgid):
            return True
        self._settled = True
        return False

    async def stop(self):
        """Stop every program still running in the tree.

        On POSIX they get SIGTERM and STOP_WAIT seconds to exit, then SIGKILL.
        Windows has no equivalent of SIGTERM for these programs, so they are
        killed at once.
        """
        if self._job is not None:
            _windows_job_kill(self._job)
            return
        if self._pgid is None or not _signal_group(self._pgid, signal.SIGTERM):
            return
        try:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + STOP_WAIT
            while loop.time() < deadline and await self.running():
                await asyncio.sleep(STOP_POLL)
        finally:
            # Also on a cancel during the wait: don't leave anything running.
            _signal_group(self._pgid, signal.SIGKILL)
            self._settled = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self._pgid is not None:
            # Cleanup was cut short (a second cancel before stop() ran): the
            # group may still have programs, so kill them before forgetting it.
            if not self._settled:
                _signal_group(self._pgid, signal.SIGKILL)
            _live_groups.discard(self._pgid)
        if self._job is not None:
            _windows_close(self._job)
            self._job = None


def _signal_group(pgid, sig):
    """Send sig to the process group; False if the group no longer exists.

    The command's pid can't be reused while its group still has members, so
    this can't reach an unrelated group.
    """
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return False
    except PermissionError:
        # A member changed its user; it can't be signalled from here.
        return True
    return True


def _live_member(pgid):
    """Whether a process in the group is running (not a zombie)."""
    for process in psutil.process_iter(["status"]):
        if process.info["status"] == psutil.STATUS_ZOMBIE:
            continue
        try:
            if os.getpgid(process.pid) == pgid:
                return True
        except OSError:
            continue  # it exited meanwhile, or can't be inspected
    return False


@atexit.register
def _kill_at_exit():
    if os.getpid() != _owner_pid:
        return
    for pgid in list(_live_groups):
        _signal_group(pgid, signal.SIGKILL)
    _live_groups.clear()


_CREATE_SUSPENDED = 0x00000004

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _ntdll = ctypes.WinDLL("ntdll")

    _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    _PROCESS_TERMINATE = 0x0001
    _PROCESS_SET_QUOTA = 0x0100
    _PROCESS_SUSPEND_RESUME = 0x0800

    class _BasicLimit(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            (field, ctypes.c_uint64)
            for field in (
                "ReadOperationCount",
                "WriteOperationCount",
                "OtherOperationCount",
                "ReadTransferCount",
                "WriteTransferCount",
                "OtherTransferCount",
            )
        ]

    class _ExtendedLimit(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimit),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _Accounting(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_int64),
            ("TotalKernelTime", ctypes.c_int64),
            ("ThisPeriodTotalUserTime", ctypes.c_int64),
            ("ThisPeriodTotalKernelTime", ctypes.c_int64),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    _kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    _kernel32.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPDWORD,
    ]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.TerminateJobObject.restype = wintypes.BOOL
    _kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    # Resumes every thread of a process started with CREATE_SUSPENDED; the
    # thread handle that ResumeThread needs is closed by subprocess.Popen.
    _ntdll.NtResumeProcess.restype = ctypes.c_long  # NTSTATUS
    _ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]

    def _check(result):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        return result

    def _new_job(process):
        job = _check(_kernel32.CreateJobObjectW(None, None))
        try:
            info = _ExtendedLimit()
            info.BasicLimitInformation.LimitFlags = (
                _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            _check(
                _kernel32.SetInformationJobObject(
                    job,
                    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                )
            )
            _check(_kernel32.AssignProcessToJobObject(job, process))
        except BaseException:
            _kernel32.CloseHandle(job)
            raise
        return job

    def _windows_attach(pid):
        """Put the suspended process in a new job, then resume it.

        Returns (job, None), or (None, error) if the job couldn't be set up;
        the process is resumed either way. Raises OSError if it can't be.
        """
        process = _check(
            _kernel32.OpenProcess(
                _PROCESS_SET_QUOTA | _PROCESS_TERMINATE | _PROCESS_SUSPEND_RESUME,
                False,
                pid,
            )
        )
        job = error = None
        try:
            job = _new_job(process)
        except OSError as job_error:
            error = job_error
        finally:
            status = _ntdll.NtResumeProcess(process)
            _kernel32.CloseHandle(process)
        if status != 0:
            if job is not None:
                _kernel32.CloseHandle(job)  # KILL_ON_JOB_CLOSE kills it too
            raise OSError(f"NtResumeProcess failed with status {status:#010x}")
        return job, error

    def _windows_job_active(job):
        info = _Accounting()
        if not _kernel32.QueryInformationJobObject(
            job,
            _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
            ctypes.byref(info),
            ctypes.sizeof(info),
            None,
        ):
            return True  # unknown: stop() then terminates the job anyway
        return info.ActiveProcesses > 0

    def _windows_job_kill(job):
        # Best effort: called during cleanup, where raising would hide the
        # original error, and closing the job (KILL_ON_JOB_CLOSE) kills its
        # programs anyway.
        _kernel32.TerminateJobObject(job, 1)

    def _windows_close(job):
        _kernel32.CloseHandle(job)
