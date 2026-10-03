# Validation for v0.2.0

Tested on 3 October 2026 on Windows with an RTX 5070 Ti Laptop GPU
(11.94 GiB VRAM), 32 GB RAM, PyTorch 2.8.0 and CUDA 12.8.

## Full image-to-mesh tests

Both runs used the bundled wolf rune axe image, seed 56, 1024 shape
resolution, 2048 texture maps and a 300,000 triangle detailed target.

| Engine | Detailed triangles | Baked model triangles | Result |
|---|---:|---:|---|
| TRELLIS.2 | 300,000 | 28,230 | Completed |
| Pixal3D shape + TRELLIS.2 materials | 300,000 | 29,278 | Completed |

Both detailed meshes passed watertightness and winding checks. Both baked
models passed watertightness after coincident UV-seam vertices were merged
for measurement. Both runs produced base color, normal, roughness, metallic,
ambient occlusion and emission maps, embedded GLB materials and a preview.

The hybrid run's shape coordinates and features were exactly equal before
and after TRELLIS.2 material sampling. Texture features were finite. This
checks preservation of the sampled shape; later repair and simplification
still modify the decoded mesh.

## Automated checks

- 21 tests passed, covering API validation, safe file access, per-version
  topology reporting, GPU limits, the memory watchdog, complex checkpoint
  buffers and resuming after a simulated decode failure.
- CUDA mesh, sparse convolution and NAF neighborhood-attention checks passed.
- PowerShell installer syntax and source packaging were checked.

## Limits

An earlier 2048 request ran out of GPU memory during mesh decoding after
sampling finished. The new preflight blocks resolutions above 1024 on the
12 GB test GPU and preserves existing checkpoints. Higher resolutions on
16 GB and 24 GB GPUs have not been validated by this project.

Memory monitoring reduces the risk of exhausting Windows memory; it cannot
guarantee protection against driver failures or every CUDA allocation.
A completely clean Windows installation has not been tested.
