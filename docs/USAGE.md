# Usage

## Pixal3D and saved stages

Run `Run.exe → Setup & download` once. In the studio select **Pixal3D shape +
TRELLIS.2 textures**. With texturing disabled, only Pixal3D geometry is produced.
The command line accepts `--engine pixal3d` with 1024 or 1536 resolution.

To resume an interrupted image job, use the library's Resume button, or run
the same image command with its original `--output` folder and `--resume`.
Resume uses the original saved settings. `shape_latents.npz` preserves the
Pixal3D geometry before TRELLIS.2 materials; `generated_latents.npz` preserves
the final sampling result before mesh decoding. `stages.json` records which
stages completed. Keep these files for recovery. Runs above the GPU memory
limit cannot resume on that GPU, including older experimental 2048 runs.

## Studio

Choose Image to 3D, upload an image, and name the result. Shape resolution
controls geometry generation; texture resolution controls the exported maps.
Keep textures enabled to produce colored GLBs. The seed controls sampling.
Keep 1024 for your first run. Stop generation cancels the worker process tree;
completed intermediate files are retained.

Repair an existing mesh accepts GLB, OBJ, PLY and STL. It creates new geometry
and removes existing materials. It does not generate new AI materials.

## Library

The library reads output folders automatically. Click a saved creation's card
to open it in the studio. Choose a model version, orbit and zoom in the viewport, and
download files. Refresh library after processing outside the app. Image-based
thumbnails show the input unless a rendered `preview.png` exists.

Each version has a separate topology result. Texture UV seams are merged only
for topology measurement; materials are not removed from the exported GLB.

## Command line

Run these from the application folder in PowerShell:

```powershell
# Full textured generation
.\.venv\Scripts\python.exe mesh_runner.py image "C:\images\object.png" --resolution 1024 --faces 300000 --texture --texture-size 2048

# Repair an existing mesh
.\.venv\Scripts\python.exe mesh_runner.py repair "C:\models\object.glb" --resolution 1024 --faces 300000

# Decode a saved sampling checkpoint after an interrupted decode
.\.venv\Scripts\python.exe mesh_runner.py decode "outputs\RUN\generated_latents.npz" --output "outputs\RUN"

# Continue from saved geometry / texture data
.\.venv\Scripts\python.exe mesh_runner.py repair "outputs\RUN\raw.ply" --output "outputs\RUN" --resolution 1024 --faces 300000
.\.venv\Scripts\python.exe mesh_runner.py texture "outputs\RUN\final.ply" --output "outputs\RUN" --faces 300000 --texture-size 2048
.\.venv\Scripts\python.exe mesh_runner.py bake "outputs\RUN\final.ply" --output "outputs\RUN" --texture-size 2048
```

Texture export requires `texture_volume.npz` from a run with texture generation
enabled. A geometry-only checkpoint cannot supply missing texture features.
CLI resolution and face defaults match the studio. Add `--texture` to enable
materials when using the command line.

Advanced flags: `--seed`, `--lowpoly-faces`, `--max-tokens`, `--proxy-points`,
`--no-quad`, and `--blender-voxel`. The extra Blender voxel pass consumes
substantial RAM and is off by default.
