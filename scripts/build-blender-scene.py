"""Blender optional exporter for the same box scene used by the Node demo.

blender -b --python scripts/build-blender-scene.py -- frontend/demo/scene.json OUTPUT
Coordinates: metres, Blender Z up; GLB converts to Y up on export.
"""
import json
from pathlib import Path
import sys
import bpy

source,destination=sys.argv[sys.argv.index('--')+1:]
scene=json.loads(Path(source).read_text(encoding='utf-8'))
out=Path(destination);out.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.scene.unit_settings.scale_length=1
for box in scene['boxes']:
    bpy.ops.mesh.primitive_cube_add(size=1,location=box['position'])
    obj=bpy.context.object;obj.name=box['name'];obj.scale=box['size']
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    material=bpy.data.materials.new(box['name']);material.use_nodes=True
    color=box['color'].lstrip('#')
    rgb=[int(color[i:i+2],16)/255 for i in (0,2,4)]
    # Convert sRGB constants to scene-linear values before assigning Principled BSDF.
    linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in rgb]
    bsdf=material.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(*linear,1)
    bsdf.inputs['Roughness'].default_value=.8
    obj.data.materials.append(material)
    for key,value in box.get('extras',{}).items():obj[key]=value
bpy.ops.wm.save_as_mainfile(filepath=str((out/'home.blend').resolve()))
bpy.ops.export_scene.gltf(filepath=str((out/'home.glb').resolve()),export_format='GLB',export_extras=True,export_yup=True)
(out/'layout.json').write_text(json.dumps(scene['layout'],ensure_ascii=False,indent=2),encoding='utf-8')
print('Exported editable scene, GLB and bindings:',out)
