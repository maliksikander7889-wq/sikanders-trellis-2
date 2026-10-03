"""Download native checkpoints, with revisions recorded for repeatable reruns."""
import argparse
import json
import time
from pathlib import Path
from native_runtime import ROOT, configure


def main():
    configure()
    from huggingface_hub import HfApi, hf_hub_download, snapshot_download
    from huggingface_hub import constants
    constants.DOWNLOAD_CHUNK_SIZE = 1024 * 1024
    parser = argparse.ArgumentParser()
    parser.add_argument("--textures", action="store_true")
    args = parser.parse_args()
    lock_path = ROOT / "model-revisions.json"
    lock = json.loads(lock_path.read_text()) if lock_path.exists() else {}
    api = HfApi()

    def revision(repo):
        if repo not in lock:
            lock[repo] = api.model_info(repo).sha
            lock_path.write_text(json.dumps(lock, indent=2) + "\n")
        return lock[repo]

    def file(repo, name, directory=None):
        print(f"Downloading {repo}/{name}", flush=True)
        for attempt in range(3):
            try:
                return hf_hub_download(repo, name, revision=revision(repo),
                                       local_dir=ROOT / "models" / (directory or repo))
            except (MemoryError, ConnectionError, TimeoutError):
                if attempt == 2:
                    raise
                print("Download interrupted; retrying from saved progress.", flush=True)
                time.sleep(3)

    repo = "microsoft/TRELLIS.2-4B"
    path = file(repo, "pipeline.json")
    config = json.loads(Path(path).read_text())
    for key, name in config["args"]["models"].items():
        if key.startswith("tex_") and not args.textures:
            continue
        if name.startswith("ckpts/"):
            source_repo, source_name = repo, name
        else:
            parts = name.split("/")
            source_repo, source_name = "/".join(parts[:2]), "/".join(parts[2:])
        for ext in ("json", "safetensors"):
            file(source_repo, f"{source_name}.{ext}")
    # This public DINOv3 source is also used by Tencent's native Pixal3D example.
    dino_repo = "camenduru/dinov3-vitl16-pretrain-lvd1689m"
    snapshot_download(dino_repo, revision=revision(dino_repo),
        allow_patterns=["*.json", "*.safetensors", "LICENSE*", "README.md"],
        local_dir=ROOT / "models/facebook/dinov3-vitl16-pretrain-lvd1689m", max_workers=1)
    bg_repo = "ZhengPeng7/BiRefNet"
    snapshot_download(bg_repo, revision=revision(bg_repo),
        allow_patterns=["*.json", "*.safetensors", "*.py", "LICENSE*", "README.md"],
        local_dir=ROOT / "models" / bg_repo, max_workers=1)
    print("Native model downloads finished.")


if __name__ == "__main__":
    main()
