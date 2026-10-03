"""Render a GLB preview with Blender: blender -b --python this.py -- in.glb out.png."""
import sys
import math
import bpy
from mathutils import Vector

source, target = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=source)
objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
points = [o.matrix_world @ Vector(c) for o in objects for c in o.bound_box]
lo = Vector([min(p[i] for p in points) for i in range(3)])
hi = Vector([max(p[i] for p in points) for i in range(3)])
center = (lo+hi)/2
size = max(hi-lo)
bpy.ops.object.camera_add(location=center + Vector((-1.0,2,0.6))*size)
camera = bpy.context.object
camera.rotation_euler = (center-camera.location).to_track_quat("-Z","Y").to_euler()
camera.data.type="ORTHO"
camera.data.ortho_scale=size*1.45
bpy.context.scene.camera=camera
for offset, power, radius in [((1,-2,3),500,3),((-2,-1,1),250,2),((0,2,2),400,2)]:
    bpy.ops.object.light_add(type="AREA",location=center+Vector(offset)*size)
    light=bpy.context.object
    light.data.energy=power*size**2
    light.data.shape="DISK"
    light.data.size=radius*size
    light.rotation_euler=(center-light.location).to_track_quat("-Z","Y").to_euler()
scene=bpy.context.scene
scene.render.engine="CYCLES"
scene.cycles.samples=32
scene.render.resolution_x=900
scene.render.resolution_y=900
scene.render.resolution_percentage=100
scene.world.color=(0.15,0.15,0.15)
scene.render.film_transparent=False
scene.render.image_settings.file_format="PNG"
scene.render.filepath=target
bpy.ops.wm.save_as_mainfile(filepath=target.rsplit(".",1)[0]+".blend")
bpy.ops.render.render(write_still=True)
