import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import * as THREE from 'three';
import {GLTFExporter} from 'three/addons/exporters/GLTFExporter.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const out=path.join(root,'dist');await fs.mkdir(out,{recursive:true});
await build({entryPoints:[path.join(root,'src/home-digital-card.js')],bundle:true,format:'esm',target:'es2022',minify:true,legalComments:'eof',outfile:path.join(out,'home-digital-card.js')});
const scene=JSON.parse(await fs.readFile(path.join(root,'demo/scene.json'),'utf8'));
const world=new THREE.Group();
const ids=new Set(scene.layout.models.map(m=>m.entity_id));
const bound=new Set();
for(const box of scene.boxes){
  const material=new THREE.MeshStandardMaterial({color:box.color,roughness:.8});
  const obj=new THREE.Mesh(new THREE.BoxGeometry(...box.size),material);
  obj.position.set(box.position[0],box.position[2],-box.position[1]);
  // Input is Blender Z-up: geometry dimensions must be swizzled for glTF Y-up.
  obj.geometry.dispose();obj.geometry=new THREE.BoxGeometry(box.size[0],box.size[2],box.size[1]);
  obj.name=box.name;obj.userData=box.extras??{};
  if(obj.userData.entity_id){if(!ids.has(obj.userData.entity_id))throw Error('Unmapped model');bound.add(obj.userData.entity_id);}
  world.add(obj);
}
if(bound.size!==ids.size)throw Error('Missing bound geometry');
// GLTFExporter uses FileReader for buffer output; Node has Blob but no FileReader.
globalThis.FileReader=class{readAsArrayBuffer(blob){blob.arrayBuffer().then(x=>{this.result=x;this.onloadend?.();});}};
const glb=await new GLTFExporter().parseAsync(world,{binary:true,onlyVisible:false});
await fs.writeFile(path.join(out,'home.glb'),Buffer.from(glb));
await fs.writeFile(path.join(out,'layout.json'),JSON.stringify(scene.layout,null,2));
for(const file of ['index.html','demo.js'])await fs.copyFile(path.join(root,'demo',file),path.join(out,file));
await fs.copyFile(path.join(root,'node_modules/three/LICENSE'),path.join(out,'THREE-LICENSE.txt'));
console.log(JSON.stringify({models:bound.size,glb_bytes:glb.byteLength,output:'frontend/dist',synthetic:true}));
