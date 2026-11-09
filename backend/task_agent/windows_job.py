"""Windows command ownership: assign a suspended process to a non-inheritable job."""

from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import msvcrt
import subprocess
from contextlib import suppress


class StartupInfo(C.Structure):
    _fields_ = [
        ("cb", W.DWORD),
        ("lpReserved", W.LPWSTR),
        ("lpDesktop", W.LPWSTR),
        ("lpTitle", W.LPWSTR),
        ("dwX", W.DWORD),
        ("dwY", W.DWORD),
        ("dwXSize", W.DWORD),
        ("dwYSize", W.DWORD),
        ("dwXCountChars", W.DWORD),
        ("dwYCountChars", W.DWORD),
        ("dwFillAttribute", W.DWORD),
        ("dwFlags", W.DWORD),
        ("wShowWindow", W.WORD),
        ("cbReserved2", W.WORD),
        ("lpReserved2", C.c_void_p),
        ("hStdInput", W.HANDLE),
        ("hStdOutput", W.HANDLE),
        ("hStdError", W.HANDLE),
    ]


class StartupInfoEx(C.Structure):
    _fields_ = [("StartupInfo", StartupInfo), ("lpAttributeList", C.c_void_p)]


class ProcessInfo(C.Structure):
    _fields_ = [
        ("hProcess", W.HANDLE),
        ("hThread", W.HANDLE),
        ("dwProcessId", W.DWORD),
        ("dwThreadId", W.DWORD),
    ]


class BasicLimits(C.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", C.c_longlong),
        ("PerJobUserTimeLimit", C.c_longlong),
        ("LimitFlags", W.DWORD),
        ("MinimumWorkingSetSize", C.c_size_t),
        ("MaximumWorkingSetSize", C.c_size_t),
        ("ActiveProcessLimit", W.DWORD),
        ("Affinity", C.c_size_t),
        ("PriorityClass", W.DWORD),
        ("SchedulingClass", W.DWORD),
    ]


class IoCounters(C.Structure):
    _fields_ = [
        (name, C.c_ulonglong)
        for name in (
            "ReadOperationCount",
            "WriteOperationCount",
            "OtherOperationCount",
            "ReadTransferCount",
            "WriteTransferCount",
            "OtherTransferCount",
        )
    ]


class ExtendedLimits(C.Structure):
    _fields_ = [
        ("BasicLimitInformation", BasicLimits),
        ("IoInfo", IoCounters),
        ("ProcessMemoryLimit", C.c_size_t),
        ("JobMemoryLimit", C.c_size_t),
        ("PeakProcessMemoryUsed", C.c_size_t),
        ("PeakJobMemoryUsed", C.c_size_t),
    ]


class Accounting(C.Structure):
    _fields_ = [
        (name, C.c_longlong)
        for name in (
            "TotalUserTime",
            "TotalKernelTime",
            "ThisPeriodTotalUserTime",
            "ThisPeriodTotalKernelTime",
        )
    ] + [
        (name, W.DWORD)
        for name in (
            "TotalPageFaultCount",
            "TotalProcesses",
            "ActiveProcesses",
            "TotalTerminatedProcesses",
        )
    ]


kernel = C.WinDLL("kernel32", use_last_error=True)


def bind(name, restype, *args):
    function = getattr(kernel, name)
    function.restype, function.argtypes = restype, args
    return function


CreateJobObject = bind("CreateJobObjectW", W.HANDLE, C.c_void_p, W.LPCWSTR)
SetJobInfo = bind(
    "SetInformationJobObject", W.BOOL, W.HANDLE, C.c_int, C.c_void_p, W.DWORD
)
QueryJobInfo = bind(
    "QueryInformationJobObject",
    W.BOOL,
    W.HANDLE,
    C.c_int,
    C.c_void_p,
    W.DWORD,
    C.c_void_p,
)
AssignJob = bind("AssignProcessToJobObject", W.BOOL, W.HANDLE, W.HANDLE)
TerminateJob = bind("TerminateJobObject", W.BOOL, W.HANDLE, W.UINT)
CloseHandle = bind("CloseHandle", W.BOOL, W.HANDLE)
CurrentProcess = bind("GetCurrentProcess", W.HANDLE)
DuplicateHandle = bind(
    "DuplicateHandle",
    W.BOOL,
    W.HANDLE,
    W.HANDLE,
    W.HANDLE,
    C.POINTER(W.HANDLE),
    W.DWORD,
    W.BOOL,
    W.DWORD,
)
InitAttributes = bind(
    "InitializeProcThreadAttributeList",
    W.BOOL,
    C.c_void_p,
    W.DWORD,
    W.DWORD,
    C.POINTER(C.c_size_t),
)
UpdateAttribute = bind(
    "UpdateProcThreadAttribute",
    W.BOOL,
    C.c_void_p,
    W.DWORD,
    C.c_size_t,
    C.c_void_p,
    C.c_size_t,
    C.c_void_p,
    C.c_void_p,
)
DeleteAttributes = bind("DeleteProcThreadAttributeList", None, C.c_void_p)
CreateProcess = bind(
    "CreateProcessW",
    W.BOOL,
    W.LPCWSTR,
    W.LPWSTR,
    C.c_void_p,
    C.c_void_p,
    W.BOOL,
    W.DWORD,
    C.c_void_p,
    W.LPCWSTR,
    C.c_void_p,
    C.POINTER(ProcessInfo),
)
ResumeThread = bind("ResumeThread", W.DWORD, W.HANDLE)
Wait = bind("WaitForSingleObject", W.DWORD, W.HANDLE, W.DWORD)
ExitCode = bind("GetExitCodeProcess", W.BOOL, W.HANDLE, C.POINTER(W.DWORD))
TerminateProcess = bind("TerminateProcess", W.BOOL, W.HANDLE, W.UINT)


def checked(result):
    if not result:
        raise C.WinError(C.get_last_error())
    return result


class WindowsJob:
    """Own stable kernel handles, never use PID snapshots as completion evidence."""

    def __init__(self, command, *, cwd, stdin_file, output_file, env):
        if not command or any(
            not isinstance(part, str) or "\0" in part for part in command
        ):
            raise ValueError("Invalid command arguments")
        self.job = self.process = None
        self.pid = None
        self.exit_code = None
        inherited = []
        attributes_ready = False
        process = ProcessInfo()
        try:
            self.job = checked(CreateJobObject(None, None))
            limits = ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = (
                0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway.
            )
            checked(SetJobInfo(self.job, 9, C.byref(limits), C.sizeof(limits)))
            for file in (stdin_file, output_file):
                handle = W.HANDLE()
                checked(
                    DuplicateHandle(
                        CurrentProcess(),
                        msvcrt.get_osfhandle(file.fileno()),
                        CurrentProcess(),
                        C.byref(handle),
                        0,
                        True,
                        2,
                    )
                )
                inherited.append(handle.value)
            handles = (W.HANDLE * len(inherited))(*inherited)
            size = C.c_size_t()
            InitAttributes(None, 1, 0, C.byref(size))
            if not size.value:
                raise C.WinError(C.get_last_error())
            attributes = C.create_string_buffer(size.value)
            checked(InitAttributes(attributes, 1, 0, C.byref(size)))
            attributes_ready = True
            checked(
                UpdateAttribute(
                    attributes,
                    0,
                    0x20002,
                    C.byref(handles),
                    C.sizeof(handles),
                    None,
                    None,
                )
            )
            startup = StartupInfoEx()
            startup.StartupInfo.cb = C.sizeof(startup)
            startup.StartupInfo.dwFlags = (
                0x100 | 0x1
            )  # STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW
            startup.StartupInfo.wShowWindow = 0
            startup.StartupInfo.hStdInput, startup.StartupInfo.hStdOutput = inherited
            startup.StartupInfo.hStdError = inherited[1]
            startup.lpAttributeList = C.cast(attributes, C.c_void_p)
            values = {str(key).upper(): str(value) for key, value in env.items()}
            if any(
                not key or "=" in key or "\0" in key + value
                for key, value in values.items()
            ):
                raise ValueError("Invalid command environment")
            environment = C.create_unicode_buffer(
                "\0".join(f"{key}={value}" for key, value in sorted(values.items()))
                + "\0\0"
            )
            command_line = C.create_unicode_buffer(subprocess.list2cmdline(command))
            flags = (
                0x4 | 0x80000 | 0x08000000 | 0x400
            )  # SUSPENDED, EXTENDED_STARTUPINFO, NO_WINDOW, UNICODE_ENVIRONMENT.
            checked(
                CreateProcess(
                    command[0],
                    command_line,
                    None,
                    None,
                    True,
                    flags,
                    environment,
                    str(cwd),
                    C.byref(startup),
                    C.byref(process),
                )
            )
            self.process, self.pid = process.hProcess, process.dwProcessId
            # No user command executes before supervision is established.
            checked(AssignJob(self.job, self.process))
            if ResumeThread(process.hThread) == 0xFFFFFFFF:
                raise C.WinError(C.get_last_error())
        except BaseException:
            if process.hProcess:
                TerminateProcess(process.hProcess, 1)
                Wait(process.hProcess, 5000)
            self.close()
            raise
        finally:
            if process.hThread:
                CloseHandle(process.hThread)
            if attributes_ready:
                DeleteAttributes(attributes)
            for handle in inherited:
                CloseHandle(handle)

    def poll(self):
        accounting = Accounting()
        checked(
            QueryJobInfo(self.job, 1, C.byref(accounting), C.sizeof(accounting), None)
        )
        wait = Wait(self.process, 0)
        if wait == 0xFFFFFFFF:
            raise C.WinError(C.get_last_error())
        if wait == 0:
            code = W.DWORD()
            checked(ExitCode(self.process, C.byref(code)))
            self.exit_code = code.value
        # An exited shell is not enough: detached children still belong to this job.
        return self.exit_code if accounting.ActiveProcesses == 0 and wait == 0 else None

    def stop(self):
        if self.job:
            checked(TerminateJob(self.job, 1))

    def close(self):
        for name in ("job", "process"):
            handle = getattr(self, name, None)
            if handle:
                CloseHandle(handle)
                setattr(self, name, None)

    def __del__(self):
        with suppress(Exception):
            self.close()
