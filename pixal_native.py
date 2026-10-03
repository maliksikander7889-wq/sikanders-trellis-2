"""Pixal3D shape generation followed by TRELLIS.2 material sampling."""
import json
import math
from pathlib import Path
from native_runtime import ROOT


def estimate_camera(image, output):
    import numpy as np
    import torch
    from moge.model.v2 import MoGeModel
    from mesh_runner import clean_memory
    print("Estimating the reference camera with MoGe 2…", flush=True)
    model = MoGeModel.from_pretrained(str(ROOT / "models/Ruicheng/moge-2-vitl/model.pt")).cuda().eval()
    with torch.inference_mode():
        tensor = torch.from_numpy(np.array(image).astype(np.float32)/255).permute(2, 0, 1).cuda()
        prediction = model.infer(tensor)
        fx = float(prediction["intrinsics"].squeeze()[0, 0])
    if not math.isfinite(fx) or fx <= 0:
        raise RuntimeError("Could not estimate a valid camera from this image. Try a clearer view of one object.")
    angle = 2 * math.atan(1 / (2 * fx))
    camera = {"camera_angle_x": angle, "distance": .5 / math.tan(angle/2), "mesh_scale": 1.0}
    (output / "camera.json").write_text(json.dumps(camera, indent=2))
    del model, tensor, prediction
    clean_memory()
    return camera


def generate_shape(args, image, pipeline, checkpoint):
    output = Path(args.output)
    camera = estimate_camera(image, output)
    pipeline.decode_latent = checkpoint
    pipeline.run_pixal3d(image, camera, seed=args.seed, pipeline_type=f"{args.resolution}_cascade",
                         max_num_tokens=args.max_tokens, generate_texture_slat=False)


def trellis_materials(args):
    import numpy as np
    import torch
    from PIL import Image
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    from trellis2.modules.sparse import SparseTensor
    from mesh_runner import save_latents
    output = Path(args.output)
    model_dir = ROOT / "models/microsoft/TRELLIS.2-4B"
    # Both models use the same shape latent convention. Fail if a future update changes it.
    pixal = json.loads((ROOT / "models/TencentARC/Pixal3D/pipeline.json").read_text())["args"]
    trellis = json.loads((model_dir / "pipeline.json").read_text())["args"]
    if pixal["shape_slat_normalization"] != trellis["shape_slat_normalization"]:
        raise RuntimeError("These Pixal3D and TRELLIS.2 checkpoints use incompatible shape latents.")
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained(str(model_dir), keep_models_loaded=False)
    pipeline.low_vram = True
    pipeline.cuda()
    with np.load(output / "shape_latents.npz", allow_pickle=False) as data:
        shape = SparseTensor(torch.from_numpy(data["shape_feats"]).cuda(), torch.from_numpy(data["shape_coords"]).cuda())
        resolution = int(data["resolution"])
    with torch.inference_mode():
        torch.manual_seed(args.seed)
        pipeline.load_image_cond_model()
        cond = pipeline.get_cond([Image.open(output / "preprocessed.png").convert("RGB")], min(resolution, 1024))
        pipeline.unload_image_cond_model()
        pipeline.load_tex_slat_flow_model_1024()
        texture = pipeline.sample_tex_slat(cond, pipeline.models["tex_slat_flow_model_1024"], shape,
                                          {"steps": 12, "guidance_strength": 1.0}, verbose=True)
        save_latents(output / "generated_latents.npz", shape, texture, resolution)
    print("TRELLIS.2 materials saved on the Pixal3D shape. Geometry latent unchanged.", flush=True)
