"""Build a source ZIP using an explicit allowlist, never local working data."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FILES=["app.py","library.py","mesh_runner.py","native_runtime.py","native_models.py",
       "prepare_runtime.py","setup.py","download_models.py","doctor.py","render_preview.py",
       "requirements.txt","sources.lock.json","model-revisions.json","README.md","LICENSE",
       "THIRD_PARTY_NOTICES.md",".gitignore","INSTALL.bat","START.bat",
       "01_INSTALL.bat","02_DOWNLOAD_MODELS.bat","03_START.bat","04_CHECK.bat",".github/FUNDING.yml"]
FOLDERS=["web","docs","examples/axe","scripts","tests"]

def release_files():
    files=[ROOT/name for name in FILES]
    for folder in FOLDERS:
        files += [p for p in (ROOT/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    for file in files:
        if not file.is_file():
            raise FileNotFoundError(file)
        if file.stat().st_size >= 95*1024**2:
            raise ValueError(f"File too large for ordinary GitHub source upload: {file}")
    return sorted(set(files))

def main():
    target=ROOT/"dist/sikanders-trellis-2.zip"
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for file in release_files():
            archive.write(file,Path("sikanders-trellis-2")/file.relative_to(ROOT))
    print(f"Created {target} ({target.stat().st_size/1024**2:.1f} MB)")

if __name__=="__main__":
    main()
