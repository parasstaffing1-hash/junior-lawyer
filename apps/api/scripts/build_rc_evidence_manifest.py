#!/usr/bin/env python3
"""Hash and inventory RC validation evidence without ingesting its contents into application logs."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--output',default='rc-evidence-manifest.json'); p.add_argument('files',nargs='+'); args=p.parse_args()
    rows=[]
    for raw in args.files:
        path=Path(raw).resolve()
        if not path.is_file(): p.error(f'not a file: {path}')
        rows.append({'filename':path.name,'size_bytes':path.stat().st_size,'sha256':digest(path)})
    rows.sort(key=lambda r:r['filename'])
    payload={'evidence':rows,'contains_secret_values':False}
    payload['snapshot_hash']=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    Path(args.output).write_text(json.dumps(payload,indent=2,sort_keys=True),encoding='utf-8')
    print(json.dumps(payload,indent=2,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
