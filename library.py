"""Read local generations without modifying their assets."""
import json
from pathlib import Path
from native_runtime import ROOT

VARIANTS = {"textured.glb": "Detailed · textured", "game_ready.glb": "Game ready · baked maps",
            "lowpoly.glb": "Low poly · textured", "final.glb": "Geometry · untextured"}

def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}

def run_path(name):
    if name == "example-axe":
        return ROOT / "examples/axe"
    root = (ROOT / "outputs").resolve()
    path = (root / str(name)).resolve()
    if path.parent != root or not path.is_dir():
        raise ValueError("Choose a saved generation.")
    return path

def records():
    result = []
    for path in sorted((ROOT / "outputs").iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_dir() or not any((path / name).exists() for name in VARIANTS):
            continue
        meta = read_json(path / "project.json")
        title = meta.get("name") or path.name.replace("_", " ").title()
        thumb = next((path / n for n in ("preview.png", "source.png", "background_removed.png", "preprocessed.png") if (path / n).exists()), ROOT / "assets/placeholder.svg")
        result.append({"id": path.name, "title": title, "thumbnail": str(thumb)})
    example = ROOT / "examples/axe"
    if (example / "game_ready.glb").exists():
        result.append({"id":"example-axe","title":"Wolf rune axe · included example","thumbnail":str(example/"preview.png")})
    return result

def files(path):
    names = ["textured.glb", "game_ready.glb", "lowpoly.glb", "final.glb", "final.stl", "final.ply",
             "mesh-audit.json", "texture-audit.json", "game-ready-audit.json", "run.log"]
    return [str(path / n) for n in names if (path / n).exists()] + [str(p) for p in sorted((path / "maps").glob("*.png"))]

def describe(path, variant):
    if variant == "textured.glb" or variant == "lowpoly.glb":
        audit = read_json(path / "texture-audit.json").get(Path(variant).stem, {})
        closed = audit.get("watertight_after_uv_weld")
    elif variant == "game_ready.glb":
        audit = read_json(path / "game-ready-audit.json")
        closed = audit.get("watertight_after_uv_weld")
    else:
        audit = read_json(path / "mesh-audit.json")
        closed = audit.get("watertight")
    faces = audit.get("faces")
    count = f"{faces:,} triangles" if faces else "Triangle count unavailable"
    state = "Watertight check passed" if closed is True else "Topology warning · not watertight" if closed is False else "Topology not verified"
    color = "Embedded materials" if variant != "final.glb" else "Geometry only · no textures"
    return f"**{count}**  ·  {color}\n\n{state}"
