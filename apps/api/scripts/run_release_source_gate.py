#!/usr/bin/env python3
"""Source-level release gate for CI and local development.

It proves deterministic tests, legal QA, migration round-trip/drift, frontend syntax, and the
static security baseline. It intentionally does NOT claim production load capacity; live load
must be run against a representative staging deployment with run_http_load.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "apps" / "api"
WEB = ROOT / "apps" / "web"
PREVIOUS_REVISION = "20260808_0027"


def run(name: str, command: list[str], cwd: Path, env: dict[str, str] | None = None) -> dict:
    started=time.perf_counter()
    proc=subprocess.run(command,cwd=cwd,env={**os.environ,**(env or {})},text=True,capture_output=True)
    return {"name":name,"passed":proc.returncode==0,"returncode":proc.returncode,"duration_ms":round((time.perf_counter()-started)*1000),"stdout":proc.stdout[-8000:],"stderr":proc.stderr[-8000:]}


def file_hash(path: Path) -> str:
    h=hashlib.sha256();
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument('--output',default=str(ROOT/'release-source-gate.json')); args=parser.parse_args()
    stages=[]
    stages.append(run('backend-tests',['python','-m','pytest','-q'],API))
    stages.append(run('legal-qa',['python','scripts/run_local_qa_gate.py'],API))
    stages.append(run('security-baseline',['python','scripts/run_security_baseline.py','--output',str(ROOT/'security-baseline-report.json')],API))
    stages.append(run('frontend-static',['node','scripts-transpile-check.cjs'],WEB))
    with tempfile.TemporaryDirectory(prefix='jl-release-migration-') as td:
        db=Path(td)/'migration.db'; env={'DATABASE_URL':f'sqlite:///{db}'}
        up=run('migration-upgrade',['alembic','upgrade','head'],API,env)
        down=run('migration-downgrade',['alembic','downgrade',PREVIOUS_REVISION],API,env) if up['passed'] else {"name":"migration-downgrade","passed":False,"returncode":1,"duration_ms":0,"stdout":"","stderr":"upgrade failed"}
        reup=run('migration-reupgrade',['alembic','upgrade','head'],API,env) if down['passed'] else {"name":"migration-reupgrade","passed":False,"returncode":1,"duration_ms":0,"stdout":"","stderr":"downgrade failed"}
        drift=run('migration-drift',['alembic','check'],API,env) if reup['passed'] else {"name":"migration-drift","passed":False,"returncode":1,"duration_ms":0,"stdout":"","stderr":"re-upgrade failed"}
        stages.extend([up,down,reup,drift])
    passed=all(s['passed'] for s in stages)
    report={"passed":passed,"mode":"source-gate","production_load_verified":False,"note":"Run scripts/run_http_load.py against representative staging before deployment approval.","stages":stages}
    raw=json.dumps(report,sort_keys=True,separators=(',',':')).encode(); report['snapshot_hash']=hashlib.sha256(raw).hexdigest()
    Path(args.output).write_text(json.dumps(report,indent=2,sort_keys=True),encoding='utf-8')
    print(json.dumps({"passed":passed,"snapshot_hash":report['snapshot_hash'],"stages":[{"name":s['name'],"passed":s['passed'],"duration_ms":s['duration_ms']} for s in stages]},indent=2))
    return 0 if passed else 1
if __name__=='__main__': raise SystemExit(main())
