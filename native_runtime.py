"""Small standalone helpers. No ComfyUI installation or server is used."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
models_dir = str(ROOT / "models")


def configure():
    sys.dont_write_bytecode = True
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in ("models", "outputs", "input", "logs", "cache", "runtime"):
        (ROOT / name).mkdir(exist_ok=True)
    os.environ.setdefault("HF_HOME", str(ROOT / "cache" / "huggingface"))
    os.environ.setdefault("TORCH_HOME", str(ROOT / "cache" / "torch"))
    os.environ.setdefault("TRITON_CACHE_DIR", str(ROOT / "cache" / "triton"))
    os.environ.setdefault("ATTN_BACKEND", "sdpa")
    os.environ.setdefault("SPARSE_ATTN_BACKEND", "sdpa")
    os.environ.setdefault("SPARSE_CONV_BACKEND", "flex_gemm")
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    os.environ.setdefault("FLEX_GEMM_AUTOTUNE_CACHE_PATH", str(ROOT / "cache" / "autotune.json"))
    sys.path.insert(0, str(ROOT / "runtime"))


class ProgressBar:
    def __init__(self, total=1):
        self.total, self.current = total, 0

    def update(self, amount=1):
        self.current += amount
        print(f"Stage progress: {self.current}/{self.total}", flush=True)

    def update_absolute(self, value, total=None, preview=None):
        self.current = value
        if total is not None:
            self.total = total


def require_memory(gib):
    """Check available Windows commit, including RAM and page file backing."""
    if os.name != "nt":
        return
    import ctypes
    class Status(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in (
                "total_phys", "avail_phys", "total_page", "avail_page",
                "total_virtual", "avail_virtual", "avail_extended")]
    status = Status()
    status.length = ctypes.sizeof(Status)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        free = status.avail_page / 2**30
        if free < gib:
            raise RuntimeError(f"Only {free:.1f} GB of Windows memory backing is available; this stage needs at least {gib} GB free. Save and close memory-heavy applications, then retry. Your input is unchanged.")


def blender_path():
    import json
    import shutil
    config = ROOT / "settings.json"
    if config.exists():
        path = json.loads(config.read_text()).get("blender")
        if path and Path(path).is_file():
            return path
    path = shutil.which("blender")
    if path:
        return path
    paths = sorted(Path("C:/Program Files/Blender Foundation").glob("Blender*/blender.exe"))
    if paths:
        return str(paths[-1])
    raise RuntimeError("Blender was not found. Set its full path in settings.json.")
