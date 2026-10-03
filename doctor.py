"""Check CUDA kernels and close an intentionally damaged test mesh."""
import argparse
import importlib
import json
import sys
from native_runtime import ROOT, blender_path, configure


def main():
    configure()
    p = argparse.ArgumentParser()
    p.add_argument("--quick", action="store_true")
    args = p.parse_args()
    import numpy as np
    import torch
    import trimesh
    assert sys.version_info[:2] == (3,12), "Python 3.12 required"
    assert torch.__version__.startswith("2.8.0"), "PyTorch 2.8.0 required"
    assert torch.version.cuda == "12.8" and torch.cuda.is_available(), "CUDA 12.8 runtime required"
    report = {"torch": torch.__version__, "gpu": torch.cuda.get_device_name(0),
              "vram_gib": torch.cuda.get_device_properties(0).total_memory / 2**30,
              "blender": blender_path()}
    for name in ("cumesh", "flex_gemm", "nvdiffrast.torch", "o_voxel", "triton", "natten", "moge.model.v2", "trellis2.pipelines.trellis2_image_to_3d", "quad_native"):
        importlib.import_module(name)
        print(f"OK: {name}", flush=True)
    naf = torch.hub.load(str(ROOT / "sources/NAF"), "naf", pretrained=False, source="local").cuda().eval()
    with torch.inference_mode():
        features = naf(torch.rand(1,3,64,64,device="cuda"), torch.rand(1,64,16,16,device="cuda"), (64,64))
        assert features.shape == (1,64,64,64) and torch.isfinite(features).all(), "NAF CUDA kernel check failed"
    del features, naf
    torch.cuda.empty_cache()
    report["naf_neighborhood_attention"] = "passed"
    import cumesh
    sphere = trimesh.creation.icosphere(subdivisions=2)
    cuda_mesh = cumesh.CuMesh()
    cuda_mesh.init(torch.tensor(sphere.vertices, dtype=torch.float32, device="cuda"),
                   torch.tensor(sphere.faces, dtype=torch.int32, device="cuda"))
    v, f = cuda_mesh.read()
    assert len(f) == len(sphere.faces)
    del cuda_mesh, v, f
    from trellis2.modules.sparse import SparseTensor, SparseConv3d
    coords = torch.tensor([[0,x,y,z] for x in range(4) for y in range(4) for z in range(4)], dtype=torch.int32, device="cuda")
    conv = SparseConv3d(8,8,3).cuda().half()
    result = conv(SparseTensor(torch.randn(64,8,device="cuda",dtype=torch.float16), coords))
    assert result.feats.shape == (64,8) and torch.isfinite(result.feats).all()
    del result, conv, coords
    torch.cuda.empty_cache()
    report["sparse_convolution"] = "passed"
    from mesh_runner import load_module
    weld = load_module("fast_weld", ROOT / "sources/FastMerge/native.py")
    assert weld.native_available(), "FastMerge DLL failed to load"
    report["cuda_mesh"] = "passed"
    if not args.quick:
        wtivo = load_module("wtivo_inprocess", ROOT / "sources/WTiVo/inprocess.py")
        sphere = trimesh.creation.icosphere(subdivisions=4, radius=0.5)
        v, f, closed, bad, elapsed = wtivo.process_arrays(sphere.vertices, sphere.faces[60:],
            input_res=256, final_res=256, proxy_points=200_000, threads=4)
        result = trimesh.Trimesh(v, f, process=False)
        assert closed and result.is_watertight and len(f), "WTiVo failed the hole-closing test"
        result.export(ROOT / "outputs/selftest_watertight.ply")
        report["hole_closing"] = {"passed": True, "seconds": elapsed, "faces": len(f)}
    report["comfyui_imported"] = any(n == "comfy" or n.startswith("comfy.") for n in sys.modules)
    assert not report["comfyui_imported"]
    (ROOT / ("logs/doctor-quick.json" if args.quick else "logs/doctor.json")).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
