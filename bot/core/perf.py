from __future__ import annotations

import os
import sys
import ctypes
from ctypes import wintypes
from typing import Dict


def _on_windows() -> bool:
    return sys.platform.startswith("win32") or sys.platform.startswith("cygwin")


def get_process_metrics() -> Dict[str, int]:
    """Return process metrics: RSS, private bytes, handle counts, GDI/USER objects.

    Values are best-effort. Keys present (bytes, counts):
    - rss_bytes
    - private_bytes (may be 0 if unavailable)
    - pagefile_bytes (fallback if private unavailable)
    - handle_count
    - gdi_count
    - user_count
    """
    out: Dict[str, int] = {
        "rss_bytes": 0,
        "private_bytes": 0,
        "pagefile_bytes": 0,
        "handle_count": 0,
        "gdi_count": 0,
        "user_count": 0,
    }
    if not _on_windows():
        try:
            # Portable fallback: use resource module for RSS (KB on Unix)
            import resource  # type: ignore
            r = resource.getrusage(resource.RUSAGE_SELF)
            rss_kb = int(getattr(r, "ru_maxrss", 0))
            out["rss_bytes"] = rss_kb * 1024
        except Exception:
            pass
        return out

    # Windows-specific via Win32 APIs
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        user32 = ctypes.WinDLL("user32", use_last_error=True)

        GetCurrentProcess = kernel32.GetCurrentProcess
        GetCurrentProcess.restype = wintypes.HANDLE

        # GetProcessHandleCount
        _GetProcessHandleCount = kernel32.GetProcessHandleCount
        _GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        _GetProcessHandleCount.restype = wintypes.BOOL

        # GetGuiResources (0=GDI, 1=USER)
        _GetGuiResources = user32.GetGuiResources
        _GetGuiResources.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        _GetGuiResources.restype = wintypes.DWORD

        # GetProcessMemoryInfo
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = PROCESS_MEMORY_COUNTERS._fields_ + [("PrivateUsage", ctypes.c_size_t)]

        _GetProcessMemoryInfo = psapi.GetProcessMemoryInfo
        # We will call with the EX structure first, fall back to base if needed

        hproc = GetCurrentProcess()

        # Handle count
        try:
            cnt = wintypes.DWORD(0)
            if _GetProcessHandleCount(hproc, ctypes.byref(cnt)):
                out["handle_count"] = int(cnt.value)
        except Exception:
            pass

        # GDI/USER object counts
        try:
            out["gdi_count"] = int(_GetGuiResources(hproc, 0))
        except Exception:
            pass
        try:
            out["user_count"] = int(_GetGuiResources(hproc, 1))
        except Exception:
            pass

        # Memory
        try:
            pmcex = PROCESS_MEMORY_COUNTERS_EX()
            pmcex.cb = ctypes.sizeof(pmcex)
            ok = _GetProcessMemoryInfo(hproc, ctypes.byref(pmcex), pmcex.cb)
            if ok:
                out["rss_bytes"] = int(pmcex.WorkingSetSize)
                out["pagefile_bytes"] = int(pmcex.PagefileUsage)
                out["private_bytes"] = int(getattr(pmcex, "PrivateUsage", 0) or 0)
            else:
                raise OSError("GetProcessMemoryInfo failed")
        except Exception:
            try:
                pmc = PROCESS_MEMORY_COUNTERS()
                pmc.cb = ctypes.sizeof(pmc)
                if _GetProcessMemoryInfo(hproc, ctypes.byref(pmc), pmc.cb):
                    out["rss_bytes"] = int(pmc.WorkingSetSize)
                    out["pagefile_bytes"] = int(pmc.PagefileUsage)
            except Exception:
                pass
    except Exception:
        pass
    return out

