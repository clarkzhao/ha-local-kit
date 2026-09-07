"""Fetch the pinned HA UI modules; no HACS or global theme required."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

parser=argparse.ArgumentParser()
parser.add_argument('destination',type=Path)
args=parser.parse_args()
args.destination.mkdir(parents=True,exist_ok=True)
manifest=Path(__file__).resolve().parents[1]/'examples/ui-assets.json'
for item in json.loads(manifest.read_text()):
    with urlopen(item['url'],timeout=60) as response:
        data=response.read()
    if hashlib.sha256(data).hexdigest()!=item['sha256']:
        raise RuntimeError('Unexpected resource checksum: '+item['name'])
    with urlopen(item['license_url'],timeout=30) as response:
        license_text=response.read()
    (args.destination/('LICENSE-'+item['name'])).write_bytes(license_text)
    target=args.destination/(item['name']+'.js')
    temp=target.with_suffix('.js.tmp');temp.write_bytes(data);temp.replace(target)
    print(item['name'],item['version'],'verified')
