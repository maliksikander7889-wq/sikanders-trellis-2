# Development

## Files

| File | Responsibility |
|---|---|
| app.py | FastAPI server, job lifecycle and local file endpoints |
| web/index.html / style.css / app.js | Custom HTML studio, visual design and browser controls |
| library.py | Safe discovery, version selection and topology summaries |
| mesh_runner.py | Generation, repair, texture export and baking workers |
| pixal_native.py | MoGe camera estimate, Pixal3D shape and TRELLIS.2 material sampling |
| resource_guard.py | Hardware preflight, GPU allocation budget and worker memory watchdog |
| native_models.py | Memory-efficient checkpoint loading |
| native_runtime.py | Local paths, memory preflight and progress adapter |
| prepare_runtime.py | Builds native adapters from pinned upstream sources |
| setup.py / scripts/install.ps1 | Python environment and Windows bootstrap |
| download_models.py | Resumable, revision-pinned model downloads |
| doctor.py | CUDA, convolution, mesh and hole-closing smoke checks |
| scripts/package_release.py | Explicit allowlist for source distribution |

## Pipeline

Image → background removal → native geometry and texture sampling → saved
latent checkpoint → decode → Quad → WTiVo → Blender reduction → safe vertex
merge → topology audit → texture projection → simplification → map baking.

The Pixal3D option replaces shape sampling and adds a separate TRELLIS.2
material worker. The material worker uses the saved shape latent directly;
it does not re-encode, regenerate or refine geometry. The pinned checkpoints
have identical shape-decoder weights and matching shape normalization.
MoGe estimates camera field of view; NAF supplies projected image features.

Each expensive stage runs in a fresh process. Atomic latent checkpoints and
`stages.json` allow resume with original settings after a worker failure.
The parent watches available RAM and Windows commit memory and stops its
own child process tree if memory becomes critically low. PyTorch workers
also reserve GPU headroom through an allocation budget. External CUDA
libraries may allocate outside PyTorch; these measures cannot guarantee
against every out-of-memory condition or driver crash.

Texture lookups project onto the original decoded surface, preventing empty
voxel sampling when the repaired surface shifts. If distance merging breaks
thin geometry, the runner accepts a conservative coincident-vertex merge only
when that surface passes watertightness and winding checks.

The app binds to loopback only. Do not expose it to the public Internet without
adding authentication and deployment hardening. No hosted service is included.

## Validation

Run `Run.exe → Check` for GPU checks, and
`python -m unittest discover -s tests` with the installed environment for
library checks. Test the UI with the bundled axe before starting a costly
generation. Full generation tests require NVIDIA hardware and model downloads.

The frontend uses a locally bundled model-viewer 4.1.0 build for orbit, zoom,
materials and GLB rendering. No frontend framework, npm install, or build step
is required to launch the application. GPU work runs in separate worker
processes; stopping a job terminates its process tree.

The current release was exercised on an existing configured Windows machine.
Bootstrap syntax, preflight, packaging and rerunnable Python setup were checked;
a completely clean Windows installation has not been tested.

## Source release

Build the Windows launcher with `powershell -File launcher/build.ps1`.
It uses the Windows .NET Framework compiler and produces `Run.exe`.
`scripts/launcher.ps1` dispatches setup, model downloads, checks and server
start/stop. Launch waits for the local API before opening the browser.
The source release contains one executable entry point and no batch files.

`python scripts/package_release.py` produces `dist/sikanders-trellis-2.zip`
from an explicit file allowlist. It includes the axe example and documentation,
but excludes local settings, logs, caches, weights and private generations.
Model and upstream code downloads happen during installation.

The lock files record actual source revisions. Keep upstream license files
when adapting or redistributing their code. Do not replace the source URLs
with branding URLs; installers need the real repositories.
