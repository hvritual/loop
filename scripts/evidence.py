"""Capture commands from the reviewed check registry; never execute issue prose."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import uuid
from scripts.common import require, read, resolve, write, digest, stable, source_digest, git

def capture(root: Path, check: str) -> dict:
    config=read(root,'.loop/checks.json')['checks']
    require(check in config,'Unknown check; register and review it before execution')
    definition=config[check]
    argv=definition.get('argv')
    require(isinstance(argv,list) and argv and all(isinstance(v,str) and v for v in argv),'Check argv must be an array, not shell text')
    timeout=definition.get('timeout_seconds',120)
    require(isinstance(timeout,int) and 0 < timeout <= 1800,'Invalid check timeout')
    argv=[sys.executable if v=='{python}' else v for v in argv]
    run_id='run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
    relative='.planning/evidence/'+run_id
    directory=resolve(root,relative); directory.mkdir(parents=True,exist_ok=False)
    before=source_digest(root)
    timed_out=False
    with (directory/'output.log').open('wb') as log:
        try:
            result=subprocess.run(argv,cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=timeout,shell=False)
            code=result.returncode
        except subprocess.TimeoutExpired:
            timed_out=True; code=124
        except OSError as exc:
            log.write(str(exc).encode()); code=127
    after=source_digest(root)
    record={'schema_version':1,'kind':'command_execution','id':run_id,'check':check,'argv':argv,'exit_code':code,'timed_out':timed_out,'source_sha256':before,'source_unchanged':before==after,'git_head':git(root,'rev-parse','HEAD',optional=True),'check_definition_sha256':stable(definition),'recorded_at':datetime.now(timezone.utc).isoformat(),'log':relative+'/output.log','log_sha256':digest(root,relative+'/output.log')}
    write(root,relative+'/result.json',record)
    return {'evidence':relative+'/result.json',**record}
