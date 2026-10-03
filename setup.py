"""Rebuild this isolated Windows environment from pinned sources."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from native_runtime import ROOT, configure


def run(*cmd):
    print(" ".join(map(str, cmd)), flush=True)
    subprocess.run(list(map(str, cmd)), check=True, cwd=ROOT)


def main():
    configure()
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Use Python 3.12; the CUDA binaries require it.")
    py = ROOT / ".venv/Scripts/python.exe"
    if not py.exists():
        run(sys.executable, "-m", "venv", ROOT / ".venv")
    uv = shutil.which("uv")
    pip = [uv, "pip", "install", "--python", str(py)] if uv else [str(py), "-m", "pip", "install"]
    run(*pip, "torch==2.8.0", "torchvision==0.23.0", "--index-url", "https://download.pytorch.org/whl/cu128")
    run(*pip, "-r", ROOT / "requirements.txt")
    lock = json.loads((ROOT / "sources.lock.json").read_text())
    for name, spec in lock.items():
        dest = ROOT / "sources" / name
        if not dest.exists():
            run("git", "clone", "--filter=blob:none", "--no-checkout", spec["url"], dest)
        # Never reset or discard edits to a downloaded source checkout.
        dirty = subprocess.check_output(["git", "-C", str(dest), "status", "--porcelain"], text=True)
        if dirty.strip():
            raise RuntimeError(f"{dest} contains edits. Preserve them before rerunning setup.")
        run("git", "-C", dest, "fetch", "--depth", "1", "origin", spec["revision"])
        if name == "Trellis-Windows":
            run("git", "-C", dest, "sparse-checkout", "set", "trellis2", "moge", "wheels/Windows/Torch280")
        run("git", "-C", dest, "checkout", "--detach", spec["revision"])
    wheels = ROOT / "sources/Trellis-Windows/wheels/Windows/Torch280"
    cc = int(subprocess.check_output([str(py), "-c", "import torch; print(torch.cuda.get_device_capability(0)[0])"], text=True).strip())
    for name in ("cumesh", "flex_gemm", "natten", "nvdiffrast", "nvdiffrec_render", "o_voxel"):
        wheel_dir = wheels / "Blackwell" if name == "natten" and cc >= 12 else wheels
        wheel = next(wheel_dir.glob(f"{name}-*-cp312-cp312-win_amd64.whl"))
        # The two NATTEN builds have the same version but different CUDA targets.
        reinstall = ["--reinstall" if uv else "--force-reinstall"] if name == "natten" else []
        run(*pip, "--no-deps", *reinstall, wheel)
    # The default WTiVo binary targets Blackwell. Older cards need its alternate archive.
    if cc < 12:
        archive = ROOT / "sources/WTiVo/build/ForNonBlackwellgpu(rtx50 and below).rar"
        run("tar", "-xf", archive, "-C", ROOT / "sources/WTiVo")
    run(py, ROOT / "prepare_runtime.py")
    run(py, ROOT / "doctor.py")
    print("Setup finished. Run 02_DOWNLOAD_MODELS.bat, then 03_START.bat.")


if __name__ == "__main__":
    main()
