"""Exercise actual npm tarball in unrelated projects; optional REAL upstream stage."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile


def execute(argv,cwd=None,expect=0):
    p=subprocess.run([str(x) for x in argv],cwd=cwd,capture_output=True,text=True,encoding='utf-8',timeout=1500,env={**os.environ,'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'})
    if p.returncode!=expect:
        logs=''
        if '--project' in argv:
            target=Path(argv[argv.index('--project')+1])
            for log in (target/'.loop-cache').glob('upstream-*.log'):
                logs+='\n'+log.name+'\n'+log.read_text(encoding='utf-8',errors='replace')[-6000:]
        out=p.stdout
        try:
            diagnostic=json.loads(out);diagnostic.pop('changed_files',None);out=json.dumps(diagnostic,ensure_ascii=False)
        except ValueError:pass
        raise RuntimeError(f'{argv}: exit {p.returncode}\n{out}\n{p.stderr}\n{logs}')
    return json.loads(p.stdout) if p.stdout.strip().startswith('{') else p.stdout


def main():
    parser=argparse.ArgumentParser();parser.add_argument('tarball',type=Path);parser.add_argument('--runtime',choices=['codex','claude','opencode']);parser.add_argument('--add-runtime');parser.add_argument('--rehome',action='store_true');args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='loop-package-') as tmp:
        base=Path(tmp)
        with tarfile.open(args.tarball) as tar:
            names=tar.getnames()
            assert not any(n.startswith(('package/.planning/','package/tests/','package/.github/')) for n in names)
            assert len([n for n in names if n.endswith('/SKILL.md')])==9, 'npm whitelist omitted skills'
            tar.extractall(base,filter='data')
        package=base/'package';target=base/'existing project';target.mkdir()
        execute(['git','init','-q',target]);(target/'AGENTS.md').write_bytes(b'# Keep my rules\r\n')
        (target/'.planning').mkdir();(target/'.planning/STATE.md').write_text('PROJECT PROGRESS')
        (target/'scripts').mkdir();(target/'scripts/loop.py').write_text('BUSINESS SCRIPT')
        cmd=['node',package/'bin/loop.cjs'];flags=['--runtime',args.runtime] if args.runtime else ['--skip-upstreams']
        first=execute(cmd+['install','--project',target]+flags)
        assert first['result']=='pass',first
        assert (target/'.planning/STATE.md').read_text()=='PROJECT PROGRESS'
        assert (target/'scripts/loop.py').read_text()=='BUSINESS SCRIPT'
        second=execute(cmd+['install','--project',target]+flags)
        assert second['changed_files']==[], 'Repeated install changed: '+str(second['changed_files'])
        doctor=execute(cmd+['doctor','--project',target]+(['--require-native'] if args.runtime else []))
        assert doctor['project_acceptance']=='needs_configuration'
        execute(cmd+['doctor','--project',target,'--require-project-checks'],expect=1)
        if args.add_runtime:
            extra=execute(cmd+['install','--project',target,'--runtime',args.add_runtime])
            assert all(v['status']=='installed' for v in extra['native'].values())
        if args.rehome:
            moved=base/'moved project';shutil.copytree(target,moved);target=moved
            execute(cmd+['doctor','--project',target,'--require-native'],expect=1)
            execute(cmd+['install','--project',target,'--runtime',args.runtime])
            execute(cmd+['doctor','--project',target,'--require-native'])
        local=['node',target/'.loop/core/bin/loop.cjs']
        execute(local+['doctor','--project',target])
        uninstall=execute(local+['uninstall','--project',target]);assert not uninstall['retained_modified']
        assert (target/'AGENTS.md').read_bytes()==b'# Keep my rules\r\n'
        assert (target/'.planning/STATE.md').read_text()=='PROJECT PROGRESS'
        assert (target/'scripts/loop.py').read_text()=='BUSINESS SCRIPT'
        print(json.dumps({'result':'pass','runtime':args.runtime or 'offline-core','package_files':len(names),'native_install_executed':bool(args.runtime),'add_runtime':args.add_runtime,'workspace_relocation_tested':args.rehome,'model_execution':False,'cases':['packed skills','install','idempotency','doctor','project preservation','local uninstall']},indent=2))

if __name__=='__main__':main()
