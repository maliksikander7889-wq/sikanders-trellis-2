# Development

## Files

| File | Responsibility |
|---|---|
| app.py | FastAPI server, job lifecycle and local file endpoints |
| web/index.html / style.css / app.js | Custom HTML studio, visual design and browser controls |
| library.py | Safe discovery, version selection and topology summaries |
| mesh_runner.py | Generation, repair, texture export and baking workers |
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

Texture lookups project onto the original decoded surface, preventing empty
voxel sampling when the repaired surface shifts. If distance merging breaks
thin geometry, the runner accepts a conservative coincident-vertex merge only
when that surface passes watertightness and winding checks.

The app binds to loopback only. Do not expose it to the public Internet without
adding authentication and deployment hardening. No hosted service is included.

## Validation

Run `04_CHECK.bat` for GPU checks, and
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

`python scripts/package_release.py` produces `dist/sikanders-trellis-2.zip`
from an explicit file allowlist. It includes the axe example and documentation,
but excludes local settings, logs, caches, weights and private generations.
Model and upstream code downloads happen during installation.

The lock files record actual source revisions. Keep upstream license files
when adapting or redistributing their code. Do not replace the source URLs
with branding URLs; installers need the real repositories.
