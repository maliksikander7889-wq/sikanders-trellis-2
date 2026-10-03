# Third-party notices

Sikander's Trellis 2 is an independent application. It uses the following
models and tools. Their authors retain ownership and their licenses apply.

| Component | Use / source |
|---|---|
| Microsoft TRELLIS.2 | [Image-to-3D model](https://github.com/microsoft/TRELLIS.2), MIT |
| VisualBruno Windows port | [Native pipeline code and CUDA wheels](https://github.com/visualbruno/ComfyUI-Trellis2), see upstream licenses |
| WTiVo | [Watertight voxel processing](https://github.com/Mstafa-awad/WTiVo-WatertightVoxel-ComfyuiNode), GPL-3.0 and bundled component notices |
| Quad reconstruction | [Surface reconstruction](https://github.com/Mstafa-awad/ComfyUI-Mesh-Quad-Reconstruct), MIT |
| LODTailor | [Mesh reduction](https://github.com/Mstafa-awad/LODTailor-The-Mesh-Trimmer-ComfyuiNode), GPL-3.0 |
| FastMerge | [Native vertex merging](https://github.com/Mstafa-awad/WTiVo-FastMergeByDistance), MIT |
| Bake Forger | [Blender texture baking](https://github.com/Mstafa-awad/LODTailor-Bake-Forger), GPL-3.0 |
| Blender | [Geometry processing and baking](https://www.blender.org/), GPL |
| Google model-viewer | [Interactive GLB viewer](https://github.com/google/model-viewer), Apache-2.0; bundled 4.1.0 license in web/vendor |
| FastAPI / Uvicorn | Local HTTP API and server; MIT / BSD-3-Clause |
| PyTorch, CuMesh, O-Voxel, FlexGEMM, nvdiffrast | GPU inference, sparse convolution, UVs and rasterization; see the downloaded sources and wheels |
| DINOv3 | Image features; downloaded from [the public model mirror](https://huggingface.co/camenduru/dinov3-vitl16-pretrain-lvd1689m); retain its model license |
| BiRefNet | [Background removal](https://huggingface.co/ZhengPeng7/BiRefNet); retain its model card and license |
| Wolf rune axe image | [Example image collection](https://github.com/Comfy-Org/workflow_templates/blob/main/input/viking_wolf_rune_axe.png), included MIT notice in examples/axe/SOURCE-LICENSE.txt |

Source repositories are pinned in `sources.lock.json`; model revisions are
pinned in `model-revisions.json`. Downloaded code remains in `sources`, and
adapted runtime files retain upstream licenses. The installer does not claim
ownership of those dependencies. Model weights are downloaded separately and
are not covered by this application's code license.

The generated axe GLB and preview are results of this application using the
credited example image. They are supplied as a demonstration, not as an
original model authored by an upstream tool's maintainers.
