"""Project-scoped file lifecycle. No model client, task scheduler or credential store.

File ownership, not a filename prefix alone, authorizes replacement/removal.
The journal is a local recovery aid, NOT a security boundary or distributed lock.
"""
from __future__ import annotations
from contextlib import contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import stat
import subprocess
import tempfile
import uuid

MANIFEST = '.loop/install-manifest.json'
JOURNAL = '.loop-cache/install-journal.json'
LOCK = '.loop-cache/install.lock'
RUNTIMES = ('codex', 'claude', 'opencode')
CORE_SCRIPTS = ('__init__.py','common.py','context.py','evidence.py','gates.py','loop.py','bootstrap.py')

class InstallError(RuntimeError):
    pass


def check(ok, message):
    if not ok: raise InstallError(message)


def sha(data): return hashlib.sha256(data).hexdigest()


def json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()


def path_at(root, relative):
    check(isinstance(relative,str) and relative and '\\' not in relative, 'Invalid relative path')
    p=PurePosixPath(relative)
    check(not p.is_absolute() and all(x not in ('..','.') for x in p.parts) and ':' not in relative, 'Unsafe path: '+relative)
    check(p.as_posix()==relative, 'Noncanonical path: '+relative)
    current=root
    for part in p.parts:
        current=current/part
        check(not current.is_symlink(), 'Symlink in managed path: '+relative)
    return current


def managed_path(relative):
    if relative in (MANIFEST,'AGENTS.md','CLAUDE.md','.gitignore','.loop/rules.json','.loop/upstreams.lock.json','.loop/checks.json','.loop/project-rules.json'):return True
    p=PurePosixPath(relative)
    return (relative.startswith(('.loop/core/','.claude/','.codex/','.opencode/','_bmad/'))
            or (len(p.parts)>=4 and p.parts[:2]==('.agents','skills') and
                (p.parts[2]=='loop' or p.parts[2].startswith(('loop-','gsd-','bmad-')))))


def project_root(project):
    root=Path(project).absolute()
    check(root.is_dir() and not root.is_symlink(), 'Project must be an existing directory, not a symlink')
    root=root.resolve()
    try:
        result=subprocess.run(['git','-C',str(root),'rev-parse','--show-toplevel'],capture_output=True,text=True,timeout=15)
    except (OSError,subprocess.TimeoutExpired) as exc:raise InstallError('Git is required: '+str(exc)) from exc
    check(result.returncode==0, 'Project must already be a Git workspace; initialize Git explicitly first')
    check(Path(result.stdout.strip()).resolve()==root, 'Use the Git workspace root, not a subdirectory')
    for ref in (MANIFEST,JOURNAL,LOCK):path_at(root,ref)
    return root


def image(root,relative):
    p=path_at(root,relative)
    if not p.exists():return None
    check(p.is_file(), 'Expected a regular file: '+relative)
    return {'data':base64.b64encode(p.read_bytes()).decode(),'mode':stat.S_IMODE(p.stat().st_mode)}


def bytes_image(data,mode=0o644):
    return {'data':base64.b64encode(data).decode(),'mode':mode}


def decode(img):return base64.b64decode(img['data'],validate=True)


def write_image(root,relative,img):
    p=path_at(root,relative)
    if img is None:
        if p.exists():p.unlink()
        return
    p.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.loop-write-',dir=p.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(decode(img));stream.flush();os.fsync(stream.fileno())
        os.chmod(name,img['mode'])
        os.replace(name,p)
    finally:
        if os.path.exists(name):os.unlink(name)


def same(a,b):
    # Windows filesystem does not preserve POSIX executable bits.
    if a is None or b is None:return a is b
    return a['data']==b['data'] and (os.name=='nt' or a['mode']==b['mode'])


def pid_alive(pid):
    if pid==os.getpid():return True
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.OpenProcess.restype=wintypes.HANDLE
        handle=api.OpenProcess(0x1000,False,pid)
        if not handle:return ctypes.get_last_error()==5
        try:
            code=wintypes.DWORD();api.GetExitCodeProcess(handle,ctypes.byref(code))
            return code.value==259
        finally:api.CloseHandle(handle)
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False
    except PermissionError:return True


@contextmanager
def project_lock(root, recovery=False):
    lock=path_at(root,LOCK);lock.parent.mkdir(parents=True,exist_ok=True)
    token=uuid.uuid4().hex
    if lock.exists():
        prior=json.loads(lock.read_text())
        stale=prior.get('host')==socket.gethostname() and not pid_alive(int(prior['pid']))
        check(recovery and stale, 'Another or interrupted installer owns the lock; inspect and run recover after it stops')
        lock.unlink()
    try:
        with lock.open('x') as f:json.dump({'pid':os.getpid(),'host':socket.gethostname(),'token':token},f)
    except FileExistsError as exc:raise InstallError('Concurrent installer detected') from exc
    try:yield
    finally:
        if lock.exists() and json.loads(lock.read_text()).get('token')==token:lock.unlink()


def load_manifest(root):
    p=path_at(root,MANIFEST)
    if not p.exists():return None
    obj=json.loads(p.read_text(encoding='utf-8'))
    check(obj.get('schema_version')==1 and obj.get('package')=='@hvritual/loop','Unknown installation manifest')
    check(isinstance(obj.get('files'),dict) and isinstance(obj.get('blocks'),dict),'Malformed installation manifest')
    check(isinstance(obj.get('runtimes'),list) and set(obj['runtimes'])<=set(RUNTIMES),'Invalid runtime manifest')
    for relative,entry in obj['files'].items():
        path_at(root,relative)
        check(managed_path(relative) and relative not in (MANIFEST,'AGENTS.md','CLAUDE.md','.gitignore','.loop/checks.json','.loop/project-rules.json'),'Invalid managed file: '+relative)
        check(re.fullmatch('[a-f0-9]{64}',entry.get('sha256','')) and entry.get('kind') in ('core','native'),'Invalid file ownership record')
    check(isinstance(obj.get('shared_files',{}),dict),'Invalid shared files registry')
    for relative,entry in obj.get('shared_files',{}).items():
        path_at(root,relative)
        check(managed_path(relative) and re.fullmatch('[a-f0-9]{64}',entry.get('sha256','')),'Invalid shared file record')
    for relative,fragment in obj['blocks'].items():
        check(relative in ('AGENTS.md','CLAUDE.md','.gitignore'),'Invalid managed block file')
        check(isinstance(fragment,str) and fragment,'Missing managed block')
        data=base64.b64decode(fragment,validate=True)
        start,end=(b'# loop:start',b'# loop:end') if relative=='.gitignore' else (b'<!-- loop:start -->',b'<!-- loop:end -->')
        check(data.count(start)==1 and data.count(end)==1 and (data.startswith(start) or data.startswith(b'\n'+start)) and data.endswith(end+b'\n'),'Invalid owned block fragment')
    return obj


def rollback(root,journal):
    check(journal.get('schema_version')==1,'Unsupported journal')
    conflicts=[]
    for op in journal['operations']:
        check(managed_path(op['path']),'Unsafe recovery path')
        current=image(root,op['path'])
        if not same(current,op['before']) and not same(current,op['after']):conflicts.append(op['path'])
    check(not conflicts,'Recovery would overwrite later edits; reconcile: '+', '.join(conflicts))
    for op in reversed(journal['operations']):
        if not same(image(root,op['path']),op['before']):write_image(root,op['path'],op['before'])
    path_at(root,JOURNAL).unlink(missing_ok=True)


def transaction(root,operations):
    if not operations:return
    check(not path_at(root,JOURNAL).exists(),'Interrupted transaction; run recover first')
    journal={'schema_version':1,'operations':operations}
    write_image(root,JOURNAL,bytes_image(json_bytes(journal),0o600))
    try:
        for op in operations:
            check(same(image(root,op['path']),op['before']),'File changed during install: '+op['path'])
            write_image(root,op['path'],op['after'])
    except Exception:
        rollback(root,journal)
        raise
    path_at(root,JOURNAL).unlink()


def recover(project):
    root=project_root(project)
    with project_lock(root,recovery=True):
        p=path_at(root,JOURNAL)
        if not p.exists():return {'result':'pass','recovered_files':[]}
        journal=json.loads(p.read_text());rollback(root,journal)
        return {'result':'pass','recovered_files':[o['path'] for o in journal['operations']]}


def validate_checks(value):
    check(isinstance(value,dict) and isinstance(value.get('checks'),dict),'Checks must contain a checks object')
    for name,definition in value['checks'].items():
        check(isinstance(name,str) and isinstance(definition,dict),'Malformed check entry')
        argv=definition.get('argv')
        check(isinstance(argv,list) and argv and all(isinstance(a,str) and a and '\x00' not in a for a in argv),'Check argv must be a nonempty argument array')
        timeout=definition.get('timeout_seconds',120)
        check(type(timeout) is int and 0<timeout<=1800,'Invalid check timeout')
    return value


def suggested_checks(root):
    result={}
    for sub in ('','backend','frontend'):
        here=root/sub
        if (here/'go.mod').is_file():result[(sub+'-' if sub else '')+'unit']={'argv':['go']+(['-C',sub] if sub else [])+['test','./...'],'timeout_seconds':120}
        p=here/'package.json'
        if p.is_file():
            try:scripts=json.loads(p.read_text(encoding='utf-8')).get('scripts',{})
            except (ValueError,UnicodeError):continue
            for name in ('test','lint','build'):
                if isinstance(scripts,dict) and name in scripts:
                    result[(sub+'-' if sub else '')+name]={'argv':['npm']+(['--prefix',sub] if sub else [])+['run',name],'timeout_seconds':120}
    return result


def source_payload(source,runtimes):
    source=Path(source)
    check((source/'.agents/skills/loop/SKILL.md').is_file(),'Use a complete distribution source/package for install or update')
    package=json.loads((source/'package.json').read_text())
    check(package['name']=='@hvritual/loop' and re.fullmatch(r'\d+\.\d+\.\d+',package['version']),'Invalid package identity/version')
    files={}
    for name in CORE_SCRIPTS:
        p=source/'scripts'/name
        check(p.is_file(),'Incomplete package: '+str(p))
        files['.loop/core/scripts/'+name]=(p.read_bytes(),0o644,'core')
    for p in sorted((source/'distribution').glob('*.py')):
        files['.loop/core/distribution/'+p.name]=(p.read_bytes(),0o644,'core')
    files['.loop/core/bin/loop.cjs']=((source/'bin/loop.cjs').read_bytes(),0o755,'core')
    files['.loop/core/package.json']=((source/'package.json').read_bytes(),0o644,'core')
    for p in sorted((source/'.agents/skills').glob('loop*/**/*')):
        if not p.is_file():continue
        check(not p.is_symlink(),'Symlink in package')
        ref=p.relative_to(source).as_posix();data=p.read_bytes()
        if p.suffix=='.md':data=data.replace(b'python scripts/',b'python .loop/core/scripts/')
        files[ref]=(data,0o644,'core')
    for name in ('rules.json','upstreams.lock.json'):
        data=(source/'.loop'/name).read_bytes()
        if name=='rules.json':
            obj=json.loads(data)
            for rule in obj['rules']:rule['origin']='.loop/core/ORIGIN.md#'+rule['id'].lower()
            data=json_bytes(obj)
        files['.loop/'+name]=(data,0o644,'core')
    files['.loop/core/ORIGIN.md']=(b'# Rule origins\n\nRules R-01 through R-12 derive from the reviewed Loop baseline at hvritual/loop commit 01dab3068c2f5810e3220541c8afabaead8007e3. No source project request, user history or approval is copied. Installation adopts the generic contract; existing project authority remains in force. The installation manifest records this package content fingerprint.\n',0o644,'core')
    files['.loop/core/INSTRUCTIONS.md']=(b'''# Loop project contract
Read existing project instructions first, then .loop/rules.json and .loop/project-rules.json. Do not weaken project constraints or infer approval from an installed file. Escalate genuine semantic conflicts.
Read .agents/skills/loop/SKILL.md; load only the phase needed. GSD is the sole progress owner; BMAD supplies analysis, not a second scheduler.
For existing work use python .loop/core/scripts/loop.py resume <ID>, reconcile .planning and real Git/CI before editing. If no state exists, discover the new intent; do not copy another project's state.
Use the project's reviewed .loop/checks.json. Empty checks and suggested_checks are not acceptance. Never execute discovered commands automatically. Framework lint is not a business test.
Never fabricate tests, review, authority or deployment. Installation and native compatibility are not live-model quality or business completion.
Upgrades/uninstall preserve project configuration and .planning. Use the distribution CLI, not direct upstream bootstrap, to update this installation. No default automatic merge.
''',0o644,'core')
    if 'claude' in runtimes:
        for name in sorted({PurePosixPath(p).parts[2] for p in files if p.startswith('.agents/skills/') and p.endswith('/SKILL.md')}):
            text=f'---\nname: {name}\ndescription: Load the canonical {name} skill for this project.\n---\n\n<!-- loop-generated-wrapper -->\nRead `.agents/skills/{name}/SKILL.md` in full from the project root. Resolve resources against that canonical directory.\n'
            files[f'.claude/skills/{name}/SKILL.md']=(text.encode(),0o644,'core')
    return package,files


def blocks_for(runtimes):
    blocks={'AGENTS.md':('<!-- loop:start -->','<!-- loop:end -->','Read `.loop/core/INSTRUCTIONS.md` and `.agents/skills/loop/SKILL.md`.\nGSD owns progress; project rules and `.planning/` remain project-specific.\nUse `node .loop/core/bin/loop.cjs doctor --project .` to check this installation.'),
            '.gitignore':('# loop:start','# loop:end','/.loop-cache/\n**/__pycache__/\n*.pyc')}
    if 'claude' in runtimes:blocks['CLAUDE.md']=('<!-- loop:start -->','<!-- loop:end -->','@AGENTS.md\nRead the canonical Loop project contract without replacing existing Claude instructions.')
    return blocks


def file_record(data,mode,kind):return {'sha256':sha(data),'mode':mode,'kind':kind}


def operation(root,ref,img):
    before=image(root,ref)
    return None if same(before,img) else {'path':ref,'before':before,'after':img}


def build_plan(root,package,files,previous,runtimes,native,checks_file):
    previous=previous or {'files':{},'blocks':{}}
    ops=[];owned={};shared={};conflicts=[];block_records={}
    for ref,(data,mode,kind) in sorted(files.items()):
        check(managed_path(ref),'Unapproved output path: '+ref)
        current=image(root,ref);old=previous['files'].get(ref)
        if old:
            if current is not None and sha(decode(current))!=old['sha256']:
                conflicts.append(ref);continue
            mode=current['mode'] if current else mode
        elif current is not None:
            if decode(current)!=data:conflicts.append(ref)
            else:shared[ref]=file_record(data,current['mode'],kind)
            continue
        owned[ref]=file_record(data,mode,kind)
        op=operation(root,ref,bytes_image(data,mode))
        if op:ops.append(op)
    for ref,old in previous['files'].items():
        if ref in files:continue
        current=image(root,ref)
        if current and sha(decode(current))!=old['sha256']:conflicts.append(ref);continue
        op=operation(root,ref,None)
        if op:ops.append(op)
    for ref,(start,end,body) in blocks_for(runtimes).items():
        current=image(root,ref);data=decode(current) if current else b''
        fragment=previous['blocks'].get(ref)
        desired=(start+'\n'+body+'\n'+end+'\n').encode()
        if fragment is not None:
            old=base64.b64decode(fragment,validate=True)
            if data.count(old)!=1:conflicts.append(ref);continue
            # Retain the exact separator used at first install.
            sep=old[:old.index(start.encode())]
            new=sep+desired;out=data.replace(old,new,1)
        else:
            if start.encode() in data or end.encode() in data:conflicts.append(ref);continue
            sep=b'\n' if data and not data.endswith(b'\n') else b''
            new=sep+desired;out=data+new
        block_records[ref]=base64.b64encode(new).decode()
        op=operation(root,ref,bytes_image(out,current['mode'] if current else 0o644))
        if op:ops.append(op)
    check(not conflicts,'Refusing to overwrite modified or unowned files: '+', '.join(sorted(conflicts)))
    # Project-owned configuration is never claimed by the installation manifest.
    config_path='.loop/checks.json';current=image(root,config_path)
    provided=validate_checks(json.loads(Path(checks_file).read_text(encoding='utf-8'))) if checks_file else None
    if current:
        existing=validate_checks(json.loads(decode(current)))
        check(provided is None or provided==existing,'Existing project checks differ; review/edit them explicitly, not through installation')
    else:
        cfg=provided or {'schema_version':1,'checks':{},'suggested_checks':suggested_checks(root),'note':'Suggestions are not approved or executed. Review and move intended definitions into checks.'}
        ops.append(operation(root,config_path,bytes_image(json_bytes(cfg))))
    if image(root,'.loop/project-rules.json') is None:
        ops.append(operation(root,'.loop/project-rules.json',bytes_image(json_bytes({'schema_version':1,'rules':[]}))))
    fingerprint=sha(json_bytes({p:sha(d) for p,(d,_,kind) in files.items() if kind=='core'}))
    manifest={'schema_version':1,'package':'@hvritual/loop','version':package['version'],'source_sha256':fingerprint,'runtimes':runtimes,'native':native,'files':owned,'blocks':block_records,'shared_files':shared,'project_config':['.loop/checks.json','.loop/project-rules.json'],'state_ownership':'project .planning; never installed, upgraded or removed'}
    op=operation(root,MANIFEST,bytes_image(json_bytes(manifest)))
    if op:ops.append(op)
    return [o for o in ops if o],manifest


def install(project,source,*,runtime=None,skip_upstreams=False,dry_run=False,checks_file=None,mode='install'):
    root=project_root(project);previous=load_manifest(root)
    check(mode in ('install','update'),'Unknown install mode')
    check(mode!='update' or previous is not None,'No existing installation to update')
    check(not path_at(root,JOURNAL).exists(),'Interrupted install; run recover first')
    check(runtime is None or runtime in RUNTIMES,'Unsupported runtime')
    runtimes=sorted(set((previous or {}).get('runtimes',[]))|{runtime or ((previous or {}).get('runtimes') or ['codex'])[0]})
    package,files=source_payload(source,runtimes)
    if previous:
        check(mode=='update' or previous['version']==package['version'],'Use update to change package versions')
        check(tuple(map(int,package['version'].split('.')))>=tuple(map(int,previous['version'].split('.'))),'Downgrade requires a reviewed migration; not performed')
    native=dict((previous or {}).get('native',{}))
    for r in runtimes:native.setdefault(r,{'status':'not_installed'})
    previous_lock=(previous or {}).get('files',{}).get('.loop/upstreams.lock.json',{}).get('sha256')
    current_lock=sha(files['.loop/upstreams.lock.json'][0])
    check(not (skip_upstreams and previous and previous_lock!=current_lock and any(v.get('status')=='installed' for v in native.values())), 'Cannot change upstream lock with --skip-upstreams; validate native upgrade first')
    reuse=previous and previous_lock==current_lock and all(v.get('status')!='installed' or v.get('project_root')==str(root) for v in native.values())
    needed=[] if skip_upstreams else [r for r in runtimes if not reuse or native[r].get('status')!='installed']
    # Reuse only integrity-checked native files. Never bless local edits as an upgrade.
    for ref,entry in (previous or {}).get('files',{}).items():
        if entry['kind']!='native':continue
        current=image(root,ref)
        check(current is not None and sha(decode(current))==entry['sha256'],'Native installation drift: '+ref)
        files[ref]=(decode(current),entry['mode'],'native')
    preview,_=build_plan(root,package,files,previous,runtimes,native,checks_file)
    if dry_run:return {'result':'pass','mode':'dry_run','planned_files':[o['path'] for o in preview],'native_staging_required':needed,'boundary':'Native outputs require staged generation; this preview performs no writes/downloads.'}
    with project_lock(root):
        # Abort instead of acting on a manifest that changed while waiting for the lock.
        check(load_manifest(root)==previous,'Installation changed concurrently; retry from fresh state')
        if needed:
            from distribution.native import stage_upstreams
            generated=stage_upstreams(root,Path(source),runtimes,files)
            files={p:v for p,v in files.items() if v[2]!='native'}
            for ref,value in generated.items():
                if ref not in files:files[ref]=value
            native={r:{'status':'installed','lock_sha256':current_lock,'project_root':str(root),'validation':'official installer artifact compatibility; not model login/execution'} for r in runtimes}
        operations,_=build_plan(root,package,files,previous,runtimes,native,checks_file)
        transaction(root,operations)
    report=doctor(root)
    return {**report,'changed_files':[o['path'] for o in operations],'operation':mode}


def doctor(project):
    root=project_root(project);manifest=load_manifest(root)
    check(manifest is not None,'Loop is not installed in this project')
    errors=[]
    if path_at(root,JOURNAL).exists():errors.append('Interrupted installation requires recover')
    for ref,entry in {**manifest.get('shared_files',{}),**manifest['files']}.items():
        current=image(root,ref)
        if current is None or sha(decode(current))!=entry['sha256'] or (os.name!='nt' and current['mode']!=entry.get('mode',current['mode'])):errors.append('Missing/modified: '+ref)
    for ref,fragment in manifest['blocks'].items():
        current=image(root,ref)
        if current is None or decode(current).count(base64.b64decode(fragment,validate=True))!=1:errors.append('Missing/modified entry block: '+ref)
    cfg=validate_checks(json.loads(path_at(root,'.loop/checks.json').read_text(encoding='utf-8')))
    native=dict(manifest['native'])
    for runtime,entry in native.items():
        if entry.get('status')!='installed':continue
        try:
            check(entry.get('lock_sha256')==sha(path_at(root,'.loop/upstreams.lock.json').read_bytes()),'Native receipt belongs to another upstream lock')
            check(entry.get('project_root')==str(root),'Workspace moved; rerun install to relocate native references')
            # Import from this release's identical contract code, not an unrelated global install.
            from scripts.bootstrap import doctor as upstream_doctor
            upstream_doctor(root,runtime)
        except Exception as exc:
            native[runtime]={**entry,'status':'invalid','reason':str(exc)};errors.append('Native '+runtime+': '+str(exc))
    return {'result':'fail' if errors else 'pass','version':manifest['version'],'integrity_errors':errors,'native':native,'project_acceptance':'configured_not_executed' if cfg['checks'] else 'needs_configuration','platform_protection':'not_verified','live_model_execution':'not_verified'}


def uninstall(project,*,dry_run=False):
    root=project_root(project);manifest=load_manifest(root)
    if manifest is None:return {'result':'pass','changed_files':[],'retained_modified':[]}
    check(not path_at(root,JOURNAL).exists(),'Interrupted install; run recover first')
    ops=[];retained=[]
    for ref,entry in manifest['files'].items():
        current=image(root,ref)
        if current and sha(decode(current))!=entry['sha256']:retained.append(ref);continue
        op=operation(root,ref,None)
        if op:ops.append(op)
    for ref,fragment in manifest['blocks'].items():
        current=image(root,ref);data=decode(current) if current else b'';old=base64.b64decode(fragment,validate=True)
        if data.count(old)!=1:
            if current:retained.append(ref)
            continue
        out=data.replace(old,b'',1)
        op=operation(root,ref,bytes_image(out,current['mode']) if out else None)
        if op:ops.append(op)
    ops.append(operation(root,MANIFEST,None))
    if not dry_run:
        with project_lock(root):
            check(load_manifest(root)==manifest,'Installation changed concurrently')
            transaction(root,ops)
    return {'result':'pass','operation':'uninstall','mode':'dry_run' if dry_run else 'applied','changed_files':[o['path'] for o in ops],'retained_modified':retained,'retained_project_state':['.planning/','.loop/checks.json','.loop/project-rules.json'],'boundary':'Only unchanged owned files removed. Native caches/account state outside project are untouched.'}
