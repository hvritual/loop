"""Generate upstream native files in an isolated project before target mutation.

Official installers still use npm/uv caches. They are not OS-sandboxed; only
recognized staged outputs are transactionally applied to the target project.
"""
from __future__ import annotations
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
from distribution.installer import InstallError, check, managed_path


def node_npx():
    node=shutil.which('node');npx=shutil.which('npx.cmd' if os.name=='nt' else 'npx')
    check(node and npx,'Native setup requires Node.js 22+ and npm/npx')
    p=subprocess.run([node,'--version'],capture_output=True,text=True,timeout=10)
    check(p.returncode==0 and int(p.stdout.strip().lstrip('v').split('.')[0])>=22,'Native setup requires Node.js 22+')
    check(shutil.which('uv'),'Native setup requires uv; install it explicitly first')
    if os.name=='nt':
        parent=Path(npx).parent
        choices=[parent/'node_modules/npm/bin/npx-cli.js',Path(node).parent/'node_modules/npm/bin/npx-cli.js']
        script=next((p for p in choices if p.is_file()),None)
        check(script is not None,'Cannot locate npx-cli.js; use an official Node/npm install')
        return [node,str(script)]
    return [npx]


def relocate(data,stage,root):
    try:text=data.decode('utf-8')
    except UnicodeError:
        check(str(stage).encode() not in data,'Unrelocatable binary native output')
        return data
    pairs={(str(stage),str(root)),(stage.as_posix(),root.as_posix()),
           (json.dumps(str(stage))[1:-1],json.dumps(str(root))[1:-1])}
    for old,new in sorted(pairs,key=lambda x:len(x[0]),reverse=True):text=text.replace(old,new)
    check(str(stage) not in text and stage.as_posix() not in text,'Staging path leaked into output')
    return text.encode('utf-8')


def stage_upstreams(root,source,runtimes,core_files):
    prefix=node_npx()
    from scripts.bootstrap import commands,constrain_bmad,wrappers,doctor
    cache=root/'.loop-cache';cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='loop-native-') as name:
        stage=Path(name)
        subprocess.run(['git','init','-q',str(stage)],check=True,timeout=15)
        for ref,(data,mode,kind) in core_files.items():
            if kind!='core':continue
            p=stage/ref;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);p.chmod(mode)
        (stage/'AGENTS.md').write_text('Use the canonical Loop skills. No project history exists in staging.\n')
        invocations=[]
        for runtime in runtimes:invocations.append(prefix+commands(stage,runtime)[0][1:])
        bmad=commands(stage,runtimes[0])[1][1:]
        lock=json.loads((stage/'.loop/upstreams.lock.json').read_text())
        bmad[bmad.index('--tools')+1]=','.join(lock['runtimes'][r]['bmad_tool'] for r in runtimes)
        invocations.append(prefix+bmad)
        for index,argv in enumerate(invocations):
            log=cache/f'upstream-{index}.log'
            with log.open('wb') as stream:
                try:
                    p=subprocess.run(argv,cwd=stage,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=900,shell=False,env={**os.environ,'PYTHONUTF8':'1'})
                except subprocess.TimeoutExpired as exc:raise InstallError('Upstream installer timed out; inspect '+str(log)) from exc
            check(p.returncode==0,'Official upstream installer failed; inspect '+str(log))
        constrain_bmad(stage)
        for runtime in runtimes:
            wrappers(stage,runtime);doctor(stage,runtime)
        generated={}
        for parent in ('.agents','.codex','.claude','.opencode','_bmad'):
            folder=stage/parent
            if not folder.exists():continue
            for p in sorted(folder.rglob('*')):
                check(not p.is_symlink(),'Unsupported symlink emitted by upstream installer: '+str(p))
                if not p.is_file() or '__pycache__' in p.parts:continue
                ref=p.relative_to(stage).as_posix()
                if ref in core_files and core_files[ref][2]=='core':continue
                check(managed_path(ref),'Unexpected native output; review before distribution: '+ref)
                generated[ref]=(relocate(p.read_bytes(),stage,root),p.stat().st_mode & 0o777,'native')
        check(generated,'No upstream installation files generated')
        return generated
