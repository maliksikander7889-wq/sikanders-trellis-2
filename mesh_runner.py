"""Native image generation, mesh processing and texture export for Sikander's Trellis 2."""
import argparse
import gc
import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from native_runtime import ROOT, ProgressBar, blender_path, configure, require_memory


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def clean_memory():
    import torch
    gc.collect()
    torch.cuda.empty_cache()


def load_mesh(path):
    import trimesh
    mesh = trimesh.load(path, force="mesh", process=False)
    if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
        raise ValueError("Input does not contain a triangle mesh.")
    return mesh


def preprocess(path, output):
    import numpy as np
    from PIL import Image, ImageOps
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGBA")
    if np.asarray(image)[:, :, 3].min() == 255:
        from trellis2.pipelines.rembg.BiRefNet import BiRefNet
        bg = ROOT / "models/ZhengPeng7/BiRefNet"
        if not (bg / "config.json").exists():
            raise RuntimeError("Background-removal model missing. Run 02_DOWNLOAD_MODELS.bat.")
        model = BiRefNet(str(bg))
        model.cuda()
        image = model(image.convert("RGB"))
        model.cpu()
        del model
        clean_memory()
    image.save(output / "background_removed.png")
    alpha = np.asarray(image)[:, :, 3]
    occupied = np.argwhere(alpha > 204)
    if not len(occupied):
        raise ValueError("No foreground found. Try a transparent PNG with a clear object.")
    y0, x0 = occupied.min(axis=0)
    y1, x1 = occupied.max(axis=0) + 1
    side = max(1, int(max(x1 - x0, y1 - y0) * 1.1))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    image = image.crop((int(cx-side/2), int(cy-side/2), int(cx-side/2)+side, int(cy-side/2)+side))
    image = image.resize((1024, 1024), Image.Resampling.LANCZOS)
    black = Image.new("RGB", image.size, "black")
    black.paste(image, mask=image.getchannel("A"))
    black.save(output / "preprocessed.png")
    return black


def generate(args):
    require_memory(12)
    import numpy as np
    import torch
    import trimesh
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    output = Path(args.output)
    model_dir = ROOT / "models/microsoft/TRELLIS.2-4B"
    if not (model_dir / "pipeline.json").exists():
        raise RuntimeError("Native checkpoints missing. Run 02_DOWNLOAD_MODELS.bat.")
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained(str(model_dir), keep_models_loaded=False)
    pipeline.low_vram = True
    pipeline.cuda()
    decode = pipeline.decode_latent
    def checkpoint_decode(shape, texture, resolution, use_tiled=True):
        data = {"shape_feats": shape.feats.float().cpu().numpy(),
                "shape_coords": shape.coords.cpu().numpy(), "resolution": resolution}
        if texture is not None:
            data.update(texture_feats=texture.feats.float().cpu().numpy(), texture_coords=texture.coords.cpu().numpy())
        np.savez(output / "generated_latents.npz", **data)
        return decode(shape, texture, resolution, use_tiled=use_tiled)
    pipeline.decode_latent = checkpoint_decode
    image = preprocess(args.input, output)
    common = {"guidance_strength": 7.5, "guidance_interval": [0.6, 1.0], "rescale_t": 3.0}
    if args.resolution in (512, 2048):
        result = pipeline.run(image, seed=args.seed, pipeline_type="512" if args.resolution == 512 else "2048_cascade",
            sparse_structure_sampler_params={"steps": 24 if args.resolution == 2048 else 12},
            shape_slat_sampler_params={"steps": 24 if args.resolution == 2048 else 12},
            max_num_tokens=args.max_tokens,
            generate_texture_slat=args.texture, fill_holes=False, keep_only_shell=False,
            pbar=ProgressBar(5), verbose=True)
    else:
        result = pipeline.run_cascade(image, seed=args.seed,
            pipeline_type=f"{args.resolution}_cascade", max_num_tokens=args.max_tokens,
            sparse_structure_resolution=32, generate_texture_slat=args.texture,
            sparse_structure_sampler_params={**common, "steps": 12, "rescale_t": 5.0, "guidance_rescale": 0.7},
            low_res_shape_slat_sampler_params={**common, "steps": 12, "guidance_rescale": 0.5},
            high_res_shape_slat_sampler_params={**common, "steps": 20, "guidance_rescale": 0.5},
            tex_slat_sampler_params={"steps": 12, "guidance_strength": 1.0},
            fill_holes=False, keep_only_shell=False, pbar=ProgressBar(5), verbose=True)
    save_generated(result[0], output, args.texture)
    print("Generation complete. Raw geometry saved.", flush=True)


def save_generated(mesh, output, with_texture):
    import numpy as np
    import trimesh
    trimesh.Trimesh(mesh.vertices.cpu().numpy(), mesh.faces.cpu().numpy(), process=False).export(output / "raw.ply")
    (output / "generation-metadata.json").write_text(json.dumps({
        "actual_resolution": round(1 / float(mesh.voxel_size)),
        "vertices": len(mesh.vertices), "faces": len(mesh.faces),
        "texture_generated": bool(with_texture)}, indent=2))
    if with_texture:
        np.savez(output / "texture_volume.npz", coords=mesh.coords.cpu().numpy(),
                 attrs=mesh.attrs.float().cpu().numpy(), voxel_size=float(mesh.voxel_size))


def decode_saved(args):
    require_memory(12)
    import numpy as np
    import torch
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    from trellis2.modules.sparse import SparseTensor
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained(str(ROOT / "models/microsoft/TRELLIS.2-4B"), keep_models_loaded=False)
    pipeline.low_vram = True
    pipeline.cuda()
    with np.load(args.input) as data:
        shape = SparseTensor(torch.from_numpy(data["shape_feats"]).cuda(), torch.from_numpy(data["shape_coords"]).cuda())
        texture = None
        if "texture_feats" in data:
            texture = SparseTensor(torch.from_numpy(data["texture_feats"]).cuda(), torch.from_numpy(data["texture_coords"]).cuda())
        resolution = int(data["resolution"])
    mesh = pipeline.decode_latent(shape, texture, resolution, use_tiled=True)[0]
    save_generated(mesh, Path(args.output), texture is not None)


def repair(args):
    require_memory(6)
    import numpy as np
    import torch
    import trimesh
    output = Path(args.output)
    mesh = load_mesh(args.input)
    if Path(args.input).suffix.lower() in (".glb", ".gltf"):
        # User GLBs are Y-up; the native generation/voxel space is Z-up.
        mesh.apply_transform([[1,0,0,0],[0,0,-1,0],[0,1,0,0],[0,0,0,1]])
    if args.quad and args.resolution != 2048:
        from quad_native import _reconstruct_item
        v, f = _reconstruct_item(torch.as_tensor(np.array(mesh.vertices), dtype=torch.float32),
            torch.as_tensor(np.array(mesh.faces), dtype=torch.int64), remesh_band=1.0,
            resolution=args.resolution, remove_floaters=True, remove_inner_faces=True)
        mesh = trimesh.Trimesh(v.numpy(), f.numpy(), process=False)
        mesh.export(output / "quad.ply")
        del v, f
        clean_memory()
    wtivo = load_module("wtivo_inprocess", ROOT / "sources/WTiVo/inprocess.py")
    points = args.proxy_points or (25_000_000 if args.resolution == 2048 else 12_000_000)
    v, f, closed, bad_edges, elapsed = wtivo.process_arrays(mesh.vertices, mesh.faces,
        input_res=args.resolution, final_res=args.resolution, proxy_points=points,
        proxy_eps_scale=1.0, proxy_feature_weight=1.5, lambda_fill=20.0,
        threads=16, thin_iso_vox=0.0, faithc_component_mode="largest")
    mesh = trimesh.Trimesh(v, f, process=False)
    mesh.export(output / "wtivo.ply")
    if not closed:
        raise RuntimeError(f"WTiVo returned {bad_edges} bad edge groups. Intermediate saved as wtivo.ply.")
    # LODTailor's own Blender script, with the workflow's cleanup parameters.
    mesh.export(output / "wtivo.glb")
    del mesh, v, f
    clean_memory()
    cmd = [blender_path(), "--background", "--factory-startup", "--python",
           str(ROOT / "sources/LODTailor/decimate_only.py"), "--",
           "--input", str(output / "wtivo.glb"), "--output", str(output / "trimmed.glb"),
           "--tris", str(args.faces), "--passes", "100", "--tolerance", "1.05",
           "--intermediate-ratio", "0.5", "--last-ratio", "0.25", "--final-ratio", "0.2",
           "--triangulate", "--relative-voxel-size", "0.001",
           "--minimum-voxel-size", "0.000001", "--seal-distance", "0.0001",
           "--seal-max-steps", "100", "--seal-keep-trying"]
    if args.blender_voxel:
        cmd.append("--voxel")
    subprocess.run(cmd, check=True, timeout=1800)
    mesh = load_mesh(output / "trimmed.glb")
    weld = load_module("fast_weld", ROOT / "sources/FastMerge/native.py")
    if not weld.native_available():
        raise RuntimeError("Native FastMerge DLL could not load. Install the Microsoft VC++ x64 runtime.")
    v, f, _, _ = weld.native_weld(mesh.vertices, mesh.faces, 1e-5, False, True)
    welded = trimesh.Trimesh(v, f, process=False)
    weld_mode = "fastmerge_1e-5"
    if not welded.is_watertight:
        # Distance welding can collapse thin architectural details. Prefer
        # the closed pre-weld surface when merging coincident export vertices.
        conservative = mesh.copy()
        conservative.merge_vertices(digits_vertex=8)
        if conservative.is_watertight and conservative.is_winding_consistent:
            welded = conservative
            weld_mode = "coincident_vertices_1e-8"
            print("Preserved thin details with conservative vertex merging.", flush=True)
    mesh = welded
    audit = {"vertices": len(mesh.vertices), "faces": len(mesh.faces),
             "watertight": bool(mesh.is_watertight), "winding_consistent": bool(mesh.is_winding_consistent),
             "wtivo_seconds": elapsed, "resolution": args.resolution, "proxy_points": points,
             "weld_mode": weld_mode}
    (output / "mesh-audit.json").write_text(json.dumps(audit, indent=2))
    mesh.export(output / "final.ply")
    mesh.export(output / "final.stl")
    glb_mesh = mesh.copy()
    glb_mesh.apply_transform([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]])
    glb_mesh.export(output / "final.glb")
    print(json.dumps(audit, indent=2), flush=True)
    if not audit["watertight"]:
        raise RuntimeError("Final mesh failed watertight verification. See mesh-audit.json; output is retained for inspection.")


def texture(args):
    import numpy as np
    import torch
    from voxel_export import to_glb
    output = Path(args.output)
    mesh = load_mesh(output / "final.ply")
    source = load_mesh(output / "raw.ply")
    source_v = torch.as_tensor(np.array(source.vertices), dtype=torch.float32, device="cuda")
    source_f = torch.as_tensor(np.array(source.faces), dtype=torch.int32, device="cuda")
    with np.load(output / "texture_volume.npz") as data:
        coords = torch.from_numpy(data["coords"]).int().cuda()
        attrs = torch.from_numpy(data["attrs"]).float().cuda()
        voxel_size = float(data["voxel_size"])
    # Bake generated PBR attributes onto the repaired surface and a low-poly copy.
    # O-Voxel may change topology during cleanup; audit each exported result.
    reports = {}
    for name, target in (("textured", args.faces), ("lowpoly", args.lowpoly_faces)):
        glb = to_glb(
            torch.as_tensor(np.array(mesh.vertices), dtype=torch.float32, device="cuda"),
            torch.as_tensor(np.array(mesh.faces), dtype=torch.int32, device="cuda"),
            attrs, coords, {"base_color": slice(0,3), "metallic": slice(3,4), "roughness": slice(4,5), "alpha": slice(5,6)},
            [[-0.5]*3, [0.5]*3], voxel_size=voxel_size, decimation_target=target,
            texture_size=args.texture_size, remesh=False, verbose=True,
            source_vertices=source_v, source_faces=source_f)
        glb.export(output / f"{name}.glb")
        geometry = glb.copy()
        geometry.merge_vertices(merge_tex=True, merge_norm=True)
        reports[name] = {"faces": len(geometry.faces), "watertight_after_uv_weld": bool(geometry.is_watertight)}
        del glb, geometry
        clean_memory()
    (output / "texture-audit.json").write_text(json.dumps(reports, indent=2))


def bake(args):
    import shutil
    output = Path(args.output)
    maps = output / "maps"
    maps.mkdir(exist_ok=True)
    settings = json.loads((ROOT / "runtime/bake-settings.json").read_text())
    for key in settings:
        if key.endswith("_resolution"):
            settings[key] = args.texture_size
    config = {"high_poly": str(output / "textured.glb"), "low_poly": str(output / "lowpoly.glb"),
              "out_dir": str(maps), "glb_out": str(maps / "baked_low.glb"),
              "result_json": str(maps / "result.json"), "settings": settings}
    config_path = maps / "config.json"
    config_path.write_text(json.dumps(config, indent=2))
    subprocess.run([blender_path(), "--background", "--factory-startup", "--python",
        str(ROOT / "runtime/bake_forger.py"), "--", str(config_path)], check=True, timeout=1800)
    if not (maps / "baked_low.glb").is_file():
        raise RuntimeError("Bake Forger did not produce its output GLB; inspect the log.")
    shutil.copy2(maps / "baked_low.glb", output / "game_ready.glb")
    mesh = load_mesh(output / "game_ready.glb")
    mesh.merge_vertices(merge_tex=True, merge_norm=True)
    (output / "game-ready-audit.json").write_text(json.dumps({"faces":len(mesh.faces),
        "watertight_after_uv_weld":bool(mesh.is_watertight)}, indent=2))


def main():
    configure()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["generate", "decode", "repair", "texture", "bake", "image"])
    p.add_argument("input", help="Image or triangle mesh path")
    p.add_argument("--output")
    p.add_argument("--resolution", type=int, choices=[512,1024,1536,2048], default=1536)
    p.add_argument("--seed", type=int, default=56)
    p.add_argument("--faces", type=int, default=6_000_000)
    p.add_argument("--lowpoly-faces", type=int, default=30_000)
    p.add_argument("--max-tokens", type=int, default=49152)
    p.add_argument("--proxy-points", type=int, default=0)
    p.add_argument("--quad", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--blender-voxel", action="store_true", help="Repeat voxel remeshing in Blender, as in the original workflow; needs more RAM")
    p.add_argument("--texture", action="store_true")
    p.add_argument("--texture-size", type=int, choices=[1024,2048,4096], default=4096)
    args = p.parse_args()
    args.input = str(Path(args.input).resolve())
    if not Path(args.input).is_file():
        p.error(f"Input file not found: {args.input}")
    if args.faces < 4 or args.lowpoly_faces < 4 or args.max_tokens < 1 or args.proxy_points < 0:
        p.error("Face counts must be >= 4; max tokens > 0; proxy points >= 0.")
    if args.output is None:
        args.output = str(ROOT / "outputs" / (Path(args.input).stem + "_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")))
    args.output = str(Path(args.output).resolve())
    Path(args.output).mkdir(parents=True, exist_ok=True)
    if args.command != "image":
        return {"generate": generate, "decode": decode_saved, "repair": repair, "texture": texture, "bake": bake}[args.command](args)
    (Path(args.output) / "run-settings.json").write_text(json.dumps(vars(args), indent=2))
    common = ["--output", args.output, "--resolution", str(args.resolution), "--seed", str(args.seed),
              "--faces", str(args.faces), "--lowpoly-faces", str(args.lowpoly_faces),
              "--max-tokens", str(args.max_tokens), "--proxy-points", str(args.proxy_points),
              "--texture-size", str(args.texture_size), "--quad" if args.quad else "--no-quad"]
    if args.texture:
        common += ["--texture"]
    if args.blender_voxel:
        common += ["--blender-voxel"]
    # Separate processes release CUDA memory fully between generation and repair.
    steps = [("generate", args.input), ("repair", str(Path(args.output) / "raw.ply"))]
    if args.texture:
        steps.append(("texture", str(Path(args.output) / "final.ply")))
        steps.append(("bake", str(Path(args.output) / "final.ply")))
    for stage, source in steps:
        subprocess.run([sys.executable, "-u", str(Path(__file__)), stage, source, *common], check=True)
    print(f"Finished. Output folder: {args.output}", flush=True)


if __name__ == "__main__":
    main()
