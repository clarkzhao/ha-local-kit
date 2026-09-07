import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
const assets=JSON.parse(await fs.readFile(new URL('../../examples/ui-assets.json',import.meta.url),'utf8'));
const out=new URL('../dist/',import.meta.url);
await fs.mkdir(new URL('../dist/',import.meta.url),{recursive:true});
for(const item of assets){
 const response=await fetch(item.url,{signal:AbortSignal.timeout(30000)});if(!response.ok)throw Error(response.status);
 const bytes=Buffer.from(await response.arrayBuffer());
 if(createHash('sha256').update(bytes).digest('hex')!==item.sha256)throw Error('Asset checksum mismatch');
 const license=await fetch(item.license_url,{signal:AbortSignal.timeout(30000)});if(!license.ok)throw Error(license.status);
 await fs.writeFile(new URL('../dist/'+item.name+'.js',import.meta.url),bytes);
 await fs.writeFile(new URL('../dist/LICENSE-'+item.name,import.meta.url),await license.text());
}
