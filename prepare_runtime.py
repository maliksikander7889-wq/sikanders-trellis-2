"""Create an adapted native library while retaining untouched upstream sources."""
import ast
import shutil
from pathlib import Path
from native_runtime import ROOT


def replace_checked(text, old, new):
    if old not in text:
        raise RuntimeError(f"Pinned source no longer matches adapter: {old[:100]}")
    return text.replace(old, new)


def main():
    dest = ROOT / "runtime" / "trellis2"
    shutil.copytree(ROOT / "sources" / "Trellis-Windows" / "trellis2", dest,
                    dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    path = dest / "pipelines" / "trellis2_image_to_3d.py"
    text = path.read_text(encoding="utf-8")
    text = replace_checked(text, "import folder_paths", "import native_runtime as folder_paths")
    text = replace_checked(text, "from comfy.utils import ProgressBar", "from native_runtime import ProgressBar")
    # Keep the large denoisers on the CPU until their sampling stage needs them.
    # The upstream cascade otherwise loads both 512 and 1024 models onto CUDA.
    for name in ("sparse_structure_flow_model", "sparse_structure_decoder",
                 "shape_slat_flow_model_512", "shape_slat_flow_model_1024",
                 "tex_slat_flow_model_512", "tex_slat_flow_model_1024",
                 "shape_slat_decoder", "tex_slat_decoder", "shape_slat_encoder"):
        text = replace_checked(text, f"self.models['{name}'].to(self._device)",
                              f"self.models['{name}'].to('cpu' if self.low_vram else self._device)")
    path.write_text(text, encoding="utf-8")
    path = dest / "models" / "sparse_structure_flow.py"
    text = path.read_text(encoding="utf-8")
    text = replace_checked(text, "torch.arange(res, device=self.device)", "torch.arange(res, device='cpu')")
    path.write_text(text, encoding="utf-8")
    path = dest / "models" / "__init__.py"
    text = path.read_text(encoding="utf-8")
    text = replace_checked(text,
        "model = __getattr__(config['name'])(**config['args'], **kwargs)\n    model.load_state_dict(load_file(model_file), strict=False)",
        "from native_models import load_checkpoint\n    model = load_checkpoint(__getattr__(config['name']), model_file, {**config['args'], **kwargs})")
    path.write_text(text, encoding="utf-8")
    path = dest / "modules" / "sparse" / "config.py"
    text = path.read_text(encoding="utf-8")
    text = replace_checked(text, "['xformers', 'flash_attn', 'flash_attn_3']",
                           "['sdpa', 'xformers', 'flash_attn', 'flash_attn_3']")
    path.write_text(text, encoding="utf-8")
    # Extract only the computational functions; exclude the ComfyUI type adapter.
    source = ROOT / "sources" / "Quad" / "nodes.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    keep = []
    excluded = {"_mesh_batch_items", "_pack_mesh_batch"}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("comfy"):
                continue
            keep.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name not in excluded:
            keep.append(node)
        elif isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) and not t.id.startswith("NODE_") for t in node.targets):
            keep.append(node)
    tree.body = keep
    (ROOT / "runtime" / "quad_native.py").write_text(ast.unparse(tree) + "\n", encoding="utf-8")
    # After watertight repair, texture lookup must project back to the original
    # generated surface. Projecting onto the repaired surface can sample empty
    # voxels and produce dark bands around small geometric offsets.
    import zipfile
    wheel = ROOT / "sources/Trellis-Windows/wheels/Windows/Torch280/o_voxel-0.0.1-cp312-cp312-win_amd64.whl"
    with zipfile.ZipFile(wheel) as archive:
        export = archive.read("o_voxel/postprocess.py").decode().replace("\r", "")
    export = replace_checked(export, "    use_tqdm: bool = False,", "    use_tqdm: bool = False,\n    source_vertices=None,\n    source_faces=None,")
    export = replace_checked(export, "bvh = cumesh.cuBVH(vertices, faces)",
        "source_vertices = vertices if source_vertices is None else source_vertices.cuda()\n    source_faces = faces if source_faces is None else source_faces.cuda()\n    bvh = cumesh.cuBVH(source_vertices, source_faces)")
    export = replace_checked(export, "orig_tri_verts = vertices[faces[face_id.long()]]", "orig_tri_verts = source_vertices[source_faces[face_id.long()]]")
    (ROOT / "runtime/voxel_export.py").write_text(export, encoding="utf-8")
    import json
    bake_tree = ast.parse((ROOT / "sources/BakeForger/__init__.py").read_text(encoding="utf-8-sig"))
    for node in bake_tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "BLENDER_BAKE_SCRIPT" for t in node.targets):
            (ROOT / "runtime/bake_forger.py").write_text(ast.literal_eval(node.value), encoding="utf-8")
        if isinstance(node, ast.ClassDef) and node.name == "LODTailorBakeForger":
            function = next(f for f in node.body if isinstance(f, ast.FunctionDef) and f.name == "INPUT_TYPES")
            inputs = ast.literal_eval(next(n.value for n in function.body if isinstance(n, ast.Return)))
            settings = {k: v[1]["default"] for k, v in inputs["required"].items() if len(v) > 1 and k != "blender_path"}
            for k in ("neutral_normal_color", "material_base_color"):
                settings[k] = [float(v) for v in settings[k].split(",")]
            for k in settings:
                if k.endswith("_resolution"):
                    settings[k] = 4096
            (ROOT / "runtime/bake-settings.json").write_text(json.dumps(settings, indent=2))
    for source_name, target_name in (("Trellis-Windows", "LICENSE-TRELLIS"), ("Quad", "LICENSE-QUAD"), ("BakeForger", "LICENSE-BAKEFORGER")):
        license_path = ROOT / "sources" / source_name / "LICENSE"
        if license_path.exists():
            shutil.copy2(license_path, ROOT / "runtime" / target_name)
    print("Native runtime prepared; upstream sources are unchanged.")


if __name__ == "__main__":
    main()
