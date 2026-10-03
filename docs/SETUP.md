# Installation and troubleshooting

## First installation

Extract the complete repository, then run `INSTALL.bat`. Do not run it from
inside a ZIP viewer. Use a writable folder outside Program Files or OneDrive.

The bootstrap uses Windows App Installer (`winget`) for missing Git, Blender
and Microsoft C++ runtime, and [uv](https://docs.astral.sh/uv/getting-started/installation/)
to install Python 3.12. It then installs pinned Python dependencies and CUDA
wheels, fetches pinned source revisions, prepares the native runtime, runs
GPU checks, and downloads geometry, image conditioning, background removal
and texture models. It does not modify an existing Python environment.

Prerequisite installers may ask Windows for permission. A current NVIDIA
driver must already be installed. If winget is missing, install Microsoft's
App Installer from Microsoft Store and run INSTALL.bat again.

`START.bat` starts the studio after setup. `04_CHECK.bat` checks the GPU and
native extensions. Advanced users can run `01_INSTALL.bat` and
`02_DOWNLOAD_MODELS.bat` separately when Python 3.12 and prerequisites exist.

## Troubleshooting

| Symptom | What to do |
|---|---|
| Missing textures | Keep texture generation enabled and open textured.glb or game_ready.glb. final.glb and STL are untextured. |
| Out of memory / paging-file error | Close memory-heavy applications; use 1024 resolution. Available system memory matters as well as VRAM. |
| Download interrupted | Rerun INSTALL.bat. Completed model files are reused. |
| Missing CUDA extension / DLL | Rerun setup, then 04_CHECK.bat. Keep Python 3.12 / PyTorch 2.8.0 / CUDA 12.8 aligned. |
| Blender not found | Install Blender or create settings.json with `{"blender":"C:/path/to/blender.exe"}`. |
| Port 7860 in use | Close the previous app terminal before launching another copy. |
| Topology warning | Use the detailed version when it passes. Inspect the relevant audit; don't assume all model versions are closed. |
| Empty foreground | Use a transparent PNG or an image with one clearly separated object. |
| Dirty source checkout | Preserve your source edits before rerunning setup. The installer refuses to discard them. |

The first fully tested configuration used Blender 5.0.1, an RTX 5070 Ti
Laptop GPU with 12 GB VRAM and 32 GB RAM. Setup can discover other Blender
versions, but they have not all been verified.

## Logs and storage

- `logs/install.log`: one-click setup transcript.
- `logs/doctor.json`: GPU/native-extension checks.
- `outputs/<creation>/run.log`: individual generation log.
- `models`, `cache`, `.venv`, `sources`, `runtime`: installation data.
- `outputs`: your work; not tracked by Git.

Before posting a log publicly, remove personal paths or filenames you do not
want to share. Model weights and your outputs are excluded from the source
release. The bundled axe example is the only included generated model.
