"""Conservative hardware limits and a memory watchdog for our worker trees."""
import os
import subprocess
import sys
import time


def gpu_info():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode == 0:
            name, total, free = result.stdout.splitlines()[0].rsplit(",", 2)
            return {"name": name.strip(), "total_gib": float(total)/1024, "free_gib": float(free)/1024}
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        pass
    return None


def resolution_limit(total_gib):
    # These are app limits, not a guarantee that every object fits in memory.
    return 2048 if total_gib >= 23 else 1536 if total_gib >= 15 else 1024


def validate_hardware(resolution, engine="trellis2", info=None):
    if engine == "pixal3d" and resolution not in (1024, 1536):
        raise ValueError("Pixal3D supports 1024 or 1536 shape resolution. Choose 1024 to start.")
    info = gpu_info() if info is None else info
    if info and resolution > resolution_limit(info["total_gib"]):
        raise ValueError(f"{resolution} exceeds this app's memory limit for your {info['total_gib']:.0f} GB GPU. "
                         f"Choose {resolution_limit(info['total_gib'])}. High resolution can exhaust memory during mesh decoding, after sampling finishes.")


def configure_gpu():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("An NVIDIA CUDA GPU is required.")
    free, total = torch.cuda.mem_get_info()
    budget = min(total * .85, free - 1024**3)
    if budget < 5 * 1024**3:
        raise RuntimeError("Less than 6 GB of GPU memory is free. Close other GPU applications and retry.")
    torch.cuda.set_per_process_memory_fraction(budget / total)


def memory_available():
    import psutil
    physical = psutil.virtual_memory().available / 1024**3
    if os.name != "nt":
        return physical, physical + psutil.swap_memory().free / 1024**3
    import ctypes
    class Status(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in ("total_phys", "avail_phys", "total_page", "avail_page",
                                                   "total_virtual", "avail_virtual", "avail_extended")]
    status = Status()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("Could not read Windows memory availability")
    return physical, status.avail_page / 1024**3


def stop_tree(process):
    import psutil
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try: child.kill()
            except psutil.NoSuchProcess: pass
        parent.kill()
    except psutil.NoSuchProcess:
        pass


def wait_worker(process):
    low_samples = 0
    while process.poll() is None:
        physical, commit = memory_available()
        low_samples = low_samples + 1 if physical < 2 or commit < 4 else 0
        if commit < 2 or low_samples >= 3:
            stop_tree(process)
            process.wait()
            raise RuntimeError("Stopped to protect Windows from running out of memory. Saved stages are retained. "
                               "Close memory-heavy apps and use 1024 resolution before retrying.")
        time.sleep(1)
    return process.returncode


def run_worker(command):
    process = subprocess.Popen(command, stdout=sys.stdout, stderr=sys.stderr,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        code = wait_worker(process)
    except BaseException:
        if process.poll() is None:
            stop_tree(process)
            process.wait()
        raise
    if code:
        raise subprocess.CalledProcessError(code, command)
