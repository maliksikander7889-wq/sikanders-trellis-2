"""Local HTTP API for the plain HTML/JavaScript Trellis studio."""
import json
import re
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from native_runtime import ROOT, configure, blender_path
import library
from resource_guard import gpu_info, resolution_limit, validate_hardware, wait_worker

configure()
app=FastAPI(title="Sikander's Trellis 2",docs_url=None,redoc_url=None)
app.mount("/web",StaticFiles(directory=ROOT/"web"),name="web")
job_lock=threading.Lock()
jobs={}
active_id=None

@app.middleware("http")
async def local_requests(request:Request,call_next):
    host=request.url.hostname
    if host not in ("127.0.0.1","localhost","testserver"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail":"Local access only"},status_code=403)
    origin=request.headers.get("origin")
    if request.method not in ("GET","HEAD","OPTIONS") and origin:
        parsed=urlsplit(origin)
        if parsed.netloc != request.headers.get("host") or parsed.scheme != request.url.scheme:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail":"Cross-site requests are not allowed"},status_code=403)
    return await call_next(request)

@app.get("/")
def index(): return FileResponse(ROOT/"web/index.html")

def asset_path(run_id,filename):
    try: root=library.run_path(run_id).resolve()
    except ValueError: raise HTTPException(404,"Creation not found")
    path=(root/filename).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in (".glb",".stl",".ply",".png",".jpg",".jpeg",".json",".log"):
        raise HTTPException(404,"Asset not found")
    return path

@app.get("/api/assets/{run_id}/{filename:path}")
def asset(run_id:str,filename:str,download:bool=False):
    path=asset_path(run_id,filename)
    return FileResponse(path,filename=path.name if download else None)

def asset_url(run_id,filename):
    from urllib.parse import quote
    return f"/api/assets/{quote(run_id,safe='')}/{quote(filename,safe='/')}"

def record_data(item):
    path=library.run_path(item["id"])
    thumb=Path(item["thumbnail"])
    versions=[]
    for name,label in library.VARIANTS.items():
        if not (path/name).exists(): continue
        if name in ("textured.glb","lowpoly.glb"):
            audit=library.read_json(path/"texture-audit.json").get(Path(name).stem,{})
        else:
            audit=library.read_json(path/("game-ready-audit.json" if name=="game_ready.glb" else "mesh-audit.json"))
        versions.append({"file":name,"label":label,"url":asset_url(item["id"],name),
                         "faces":audit.get("faces"),"watertight":audit.get("watertight",audit.get("watertight_after_uv_weld")),
                         "bytes":(path/name).stat().st_size})
    return {"id":item["id"],"name":item["title"],"example":item["id"]=="example-axe",
            "thumbnail":asset_url(item["id"],thumb.name) if thumb.parent==path else "/web/placeholder.svg",
            "versions":versions,"files":[{"name":str(Path(p).relative_to(path)).replace('\\','/'),
                "url":asset_url(item["id"],str(Path(p).relative_to(path)).replace('\\','/'))} for p in library.files(path)]}

@app.get("/api/library")
def get_library(): return [record_data(item) for item in library.records()]

@app.get("/api/system")
def system():
    info = gpu_info()
    return {"gpu":info["name"] if info else "NVIDIA GPU required", "available":bool(info),
            "engine":"TRELLIS.2 + Pixal3D", "cpu_supported":False,
            "max_resolution":resolution_limit(info["total_gib"]) if info else 1024,
            "vram_gib":round(info["total_gib"],1) if info else None,
            "pixal3d_ready":(ROOT/"models/pixal3d-ready.json").is_file()}

def public_job(job):
    path=ROOT/"outputs"/job["id"]
    log=path/"run.log"
    text=log.read_text(encoding="utf-8",errors="replace")[-18000:] if log.exists() else "Preparing generation…"
    return {k:job[k] for k in ("id","name","state","started","message")} | {"log":text,"elapsed":round(time.time()-job["started"]),
            "engine":library.read_json(path/"run-settings.json").get("engine","trellis2")}

@app.get("/api/jobs/current")
def current_job():
    with job_lock:
        return public_job(jobs[active_id]) if active_id else None

@app.get("/api/jobs/{job_id}")
def get_job(job_id:str):
    with job_lock:
        if job_id not in jobs: raise HTTPException(404,"Job not found")
        return public_job(jobs[job_id])

def execute_job(job,command):
    global active_id
    output=ROOT/"outputs"/job["id"]
    try:
        with (output/"run.log").open("a",encoding="utf-8") as log:
            with job_lock:
                if job["state"]=="cancelled": return
                process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                job["process"]=process
            code=wait_worker(process)
            with job_lock:
                cancelled=job["state"]=="cancelled"
            if cancelled: return
            if code:
                detail=(output/"run.log").read_text(encoding="utf-8",errors="replace")[-24000:]
                if "out of memory" in detail.lower():
                    raise RuntimeError("GPU memory ran out. Saved stages are retained. Use 1024 resolution and close other GPU apps; see the log for the failed stage.")
                raise RuntimeError("Processing stopped. See the generation log for details; intermediate files are saved.")
            best=next((output/v for v in library.VARIANTS if (output/v).exists()),None)
            if best:
                with job_lock: job["message"]="Rendering your library preview…"
                try:
                    with job_lock:
                        if job["state"]=="cancelled": return
                        process=subprocess.Popen([blender_path(),"--background","--factory-startup","--python",str(ROOT/"render_preview.py"),"--",str(best),str(output/"preview.png")],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                        job["process"]=process
                    process.wait(timeout=180)
                except (OSError,RuntimeError,subprocess.TimeoutExpired) as exc:
                    if process.poll() is None: subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],capture_output=True)
                    print(f"Preview unavailable: {exc}",file=log)
            with job_lock:
                if job["state"]!="cancelled":
                    job.update(state="complete",message="Your creation is ready.")
    except Exception as exc:
        with job_lock:
            if job["state"]!="cancelled": job.update(state="failed",message=str(exc))
    finally:
        with job_lock:
            job.pop("process",None)
            active_id=None
        (output/"job-status.json").write_text(json.dumps({k:v for k,v in job.items() if k!="process"}),encoding="utf-8")

@app.post("/api/jobs")
async def create_job(file:UploadFile=File(...),name:str=Form("Untitled creation"),task:str=Form("image"),
                     resolution:int=Form(1024),texture_size:int=Form(2048),seed:int=Form(56),
                     faces:int=Form(300000),texture:bool=Form(True),quad:bool=Form(True),engine:str=Form("trellis2")):
    global active_id
    if engine not in ("trellis2","pixal3d") or task not in ("image","repair") or resolution not in (1024,1536,2048) or texture_size not in (1024,2048,4096) or not 4<=faces<=6000000 or not 0<=seed<=2147483647:
        raise HTTPException(422,"Invalid generation settings")
    if task == "repair": engine = "trellis2"
    try: validate_hardware(resolution,engine)
    except ValueError as exc: raise HTTPException(422,str(exc))
    if engine == "pixal3d" and not (ROOT/"models/pixal3d-ready.json").is_file():
        raise HTTPException(422,"Pixal3D needs its additional models. Run Run.exe → Setup & download once, then refresh this page.")
    suffix=Path(file.filename or "").suffix.lower()
    allowed=(".png",".jpg",".jpeg",".webp") if task=="image" else (".glb",".ply",".stl",".obj")
    if suffix not in allowed: raise HTTPException(422,"Unsupported input file")
    label=name.strip()[:80] or "Untitled creation"
    slug=re.sub(r"[^a-z0-9]+","-",label.lower()).strip("-")[:45] or "creation"
    job_id=datetime.now().strftime("%Y%m%d_%H%M%S_%f")+"_"+slug
    with job_lock:
        if active_id: raise HTTPException(409,"A generation is already running. Stop it or wait for it to finish.")
        active_id=job_id
        job={"id":job_id,"name":label,"state":"running","started":time.time(),"message":"Generating your asset…"}
        jobs[job_id]=job
    output=ROOT/"outputs"/job_id
    output.mkdir()
    try:
        source=output/("source"+suffix)
        limit=30*1024**2 if task=="image" else 512*1024**2
        total=0
        with source.open("wb") as stream:
            while chunk:=await file.read(1024**2):
                total+=len(chunk)
                if total>limit: raise HTTPException(413,"Input is too large (30 MB for images, 512 MB for meshes)")
                stream.write(chunk)
        if task=="image":
            from PIL import Image,ImageOps
            try:
                with Image.open(source) as image:
                    ImageOps.exif_transpose(image).convert("RGBA").save(output/"source.png")
            except (OSError,ValueError,Image.DecompressionBombError):
                raise HTTPException(422,"This image could not be read. Choose a valid PNG, JPG or WEBP.")
            source=output/"source.png"
        (output/"project.json").write_text(json.dumps({"name":label,"task":task,"created":datetime.now().isoformat()}),encoding="utf-8")
        command=[sys.executable,"-u",str(ROOT/"mesh_runner.py"),task,str(source),"--engine",engine,"--output",str(output),"--resolution",str(resolution),"--texture-size",str(texture_size),"--seed",str(seed),"--faces",str(faces),"--quad" if quad else "--no-quad"]
        if texture and task=="image": command += ["--texture"]
        threading.Thread(target=execute_job,args=(job,command),daemon=True).start()
        return {"id":job_id}
    except Exception:
        with job_lock:
            active_id=None
            job.update(state="failed",message="Could not read the uploaded input.")
        raise
    finally: await file.close()

@app.post("/api/jobs/{job_id}/stop")
def stop_job(job_id:str):
    with job_lock:
        job=jobs.get(job_id)
        if not job or job["state"]!="running": raise HTTPException(409,"This generation is not running")
        job.update(state="cancelled",message="Generation stopped. Intermediate files have been retained.")
        process=job.get("process")
        if process and process.poll() is None:
            subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],capture_output=True)
    return {"state":"cancelled"}


@app.get("/api/recovery")
def recovery_runs():
    result=[]
    info=gpu_info()
    for path in sorted((ROOT/"outputs").iterdir(),reverse=True):
        if path.name == active_id: continue
        if not path.is_dir() or not (path/"run-settings.json").is_file(): continue
        settings=library.read_json(path/"run-settings.json")
        status=library.read_json(path/"job-status.json")
        if status.get("state")=="complete" or ((path/"game_ready.glb").exists() and (path/"game-ready-audit.json").exists()): continue
        if not settings.get("texture") and library.read_json(path/"mesh-audit.json").get("watertight") is True: continue
        if not any((path/name).exists() for name in ("shape_latents.npz","generated_latents.npz")): continue
        blocked=None
        try: validate_hardware(settings.get("resolution",1024),settings.get("engine","trellis2"),info)
        except ValueError as exc: blocked=str(exc)
        result.append({"id":path.name,"name":library.read_json(path/"project.json").get("name",path.name),
                       "resolution":settings.get("resolution",1024),"blocked_reason":blocked})
    return result


@app.post("/api/recovery/{run_id}")
def resume_run(run_id:str):
    global active_id
    try: output=library.run_path(run_id)
    except ValueError as exc: raise HTTPException(404,str(exc))
    settings=library.read_json(output/"run-settings.json")
    if not settings or not (output/"source.png").is_file():
        raise HTTPException(422,"This run has no saved image settings to resume.")
    try: validate_hardware(settings.get("resolution",1024),settings.get("engine","trellis2"))
    except ValueError as exc: raise HTTPException(422,str(exc))
    with job_lock:
        if active_id: raise HTTPException(409,"A generation is already running.")
        active_id=run_id
        job={"id":run_id,"name":library.read_json(output/"project.json").get("name",run_id),
             "state":"running","started":time.time(),"message":"Resuming saved stages…"}
        jobs[run_id]=job
    command=[sys.executable,"-u",str(ROOT/"mesh_runner.py"),"image",str(output/"source.png"),"--output",str(output),"--resume"]
    threading.Thread(target=execute_job,args=(job,command),daemon=True).start()
    return {"id":run_id}

if __name__=="__main__":
    import uvicorn
    threading.Timer(1.5,lambda:webbrowser.open("http://127.0.0.1:7860")).start()
    uvicorn.run(app,host="127.0.0.1",port=7860,log_level="warning")
